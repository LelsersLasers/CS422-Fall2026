// SPDX-License-Identifier: GPL-2.0-only
/**
 * @file tcp_rla.c
 * @brief RTT-Loss AIMD (RLA), a loadable Linux TCP congestion controller.
 *
 * RLA combines three signals: increasing RTT suggests queueing, native TCP
 * congestion feedback triggers loss backoff, and acknowledged throughput tells
 * us whether the existing window is being used enough to justify growing it.
 * After slow start, normal decisions happen once per control interval (epoch).
 *
 * The helpers below compute window changes; the Linux callbacks near the bottom
 * connect those decisions to a live socket. Linux still owns ACK processing,
 * retransmission, proportional rate reduction (PRR), explicit congestion
 * notification (ECN), retransmission timeouts (RTO), and pacing. RLA does not
 * implement a second TCP stack or change the system's default algorithm.
 *
 * See Assignment2/part3b-writeup.tex for the design and its limitations.
 */

#include <linux/build_bug.h>
#include <linux/module.h>
#include <net/tcp.h>

/**
 * Minimum control interval: 100 ms avoids reacting to every individual ACK.
 */
#define RLA_MIN_EPOCH_US (100000U)

/**
 * Normal window floor; Linux may temporarily use one segment after an RTO.
 */
#define RLA_MIN_CWND (2U)

/**
 * @brief Per-connection history in Linux's congestion-control private area.
 *
 * An epoch is one measurement interval. Its starting window, MSS, and RTT are
 * saved together so the utilization check has a consistent reference point.
 */
struct rla_state
{
    u64 epoch_us;          /**< Monotonic timestamp at epoch start, in us. */
    u64 epoch_bytes;       /**< Cumulative acknowledged bytes at epoch start. */
    u32 min_rtt_us;        /**< Lowest positive SRTT; zero means unknown. */
    u32 epoch_rtt_us;      /**< Starting smoothed RTT, in us. */
    u32 epoch_cwnd;        /**< Starting congestion window, in segments. */
    u32 epoch_mss;         /**< Starting maximum segment size, in bytes. */
    u32 epoch_duration_us; /**< max(100 ms, start RTT), fixed for the epoch. */
    bool epoch_valid;      /**< Whether the start measurements can be used. */
};

/**
 * @brief Snapshot of the live TCP state needed for one normal ACK decision.
 */
struct rla_input
{
    u64 now_us;        /**< Current monotonic ACK timestamp, in us. */
    u64 bytes_acked;   /**< Cumulative acknowledged-byte counter. */
    u32 rtt_us;        /**< Current positive SRTT, in us, unscaled. */
    u32 cwnd;          /**< Current congestion window, in segments. */
    u32 mss;           /**< Current sender MSS, in bytes. */
    u32 ssthresh;      /**< Threshold separating slow start from avoidance. */
    u32 clamp;         /**< Linux's maximum permitted window, in segments. */
    u32 acked;         /**< New ACKed/delivered segments passed by TCP. */
    bool cwnd_limited; /**< Whether TCP considers the sender window-limited. */
};

/**
 * @brief Reason for the decision, also used to recognize delay backoff.
 */
enum rla_action
{
    RLA_HOLD,    /**< Keep the current window and threshold. */
    RLA_STARTUP, /**< ACK-driven slow-start growth. */
    RLA_ADD,     /**< One-segment additive probe after a completed epoch. */
    RLA_DELAY    /**< Multiplicative decrease because RTT is too high. */
};

/**
 * @brief Updated values for the callback to write back into the TCP socket.
 */
struct rla_decision
{
    u32 cwnd;               /**< Resulting window, in segments. */
    u32 ssthresh;           /**< Resulting slow-start threshold, in segments. */
    enum rla_action action; /**< Which update rule was selected. */
};

/**
 * @brief Compute the threshold requested for native congestion recovery.
 * @param cwnd Current window, in segments.
 * @return Half the window, rounded down, with a two-segment minimum.
 *
 * The stronger 50% reduction is reserved for native congestion feedback;
 * delay-only backoff below is a gentler 10% reduction.
 */
static inline u32 rla_loss_window(u32 cwnd)
{
    return cwnd / 2 < RLA_MIN_CWND ? RLA_MIN_CWND : cwnd / 2;
} /* rla_loss_window() */

/**
 * @brief Discard measurements that span recovery or an idle restart.
 * @param ca This connection's RLA history.
 *
 * Keep the lifetime RTT baseline, but make the next normal ACK start a fresh
 * epoch. Otherwise recovery traffic could distort utilization or trigger an
 * extra delay decrease based on measurements from before the native backoff.
 */
static inline void rla_reset_epoch(struct rla_state *ca)
{
    /* Preserve the lifetime minimum; discard an idle/recovery-mixed epoch. */
    ca->epoch_valid = false;
} /* rla_reset_epoch() */

/**
 * @brief Multiply two unsigned values only when the result fits in 64 bits.
 * @param a First factor.
 * @param b Second factor.
 * @param out Receives the product on success; unchanged on overflow.
 * @return true on success, false if the multiplication would overflow.
 */
static inline bool rla_multiply(u64 a, u64 b, u64 *out)
{
    /* Check before multiplying; zero is safe and must not cause a
     * division by zero. */
    if ((b != 0) && (a > (~(u64)0) / b)) {
        return false;
    }
    *out = a * b;
    return true;
} /* rla_multiply() */

/**
 * @brief Check whether ACKed throughput uses at least 80% of the starting
 * window.
 * @param ca Epoch-start reference measurements.
 * @param bytes Newly acknowledged bytes during this epoch.
 * @param dt Actual elapsed time during this epoch, in us; must be positive.
 * @return true if utilization is at least 80%; false on low use or overflow.
 *
 * Throughput alone cannot identify bottleneck capacity. Here it only gates
 * growth: enlarging a poorly utilized window may not help an application- or
 * receiver-limited sender. False means hold, not a loss response.
 */
static inline bool rla_busy(const struct rla_state *ca, u64 bytes, u64 dt)
{
    u64 lhs = 0;
    u64 rhs = 0;

    /*
     * utilization = (bytes / dt) /
     * (starting_cwnd * starting_MSS / starting_RTT).
     * Comparing against 4/5 gives 5*bytes*RTT >= 4*dt*cwnd*MSS.
     * This avoids floating point in the kernel; bits/byte and us/s cancel.
     * Overflow means "not enough trustworthy evidence to grow".
     */
    if ((rla_multiply(bytes, ca->epoch_rtt_us, &lhs)) &&
        (rla_multiply(lhs, 5, &lhs)) &&
        (rla_multiply(dt, ca->epoch_cwnd, &rhs)) &&
        (rla_multiply(rhs, ca->epoch_mss, &rhs)) &&
        (rla_multiply(rhs, 4, &rhs))) {
        return lhs >= rhs;
    }
    return false;
} /* rla_busy() */

/**
 * @brief Capture the baseline for a new measurement interval.
 * @param ca History to update.
 * @param in Current valid socket measurements.
 * @param cwnd Window to use as the reference, including any decision just made.
 */
static inline void rla_begin_epoch(struct rla_state *ca,
                                   const struct rla_input *in, u32 cwnd)
{
    ca->epoch_us = in->now_us;
    ca->epoch_bytes = in->bytes_acked;
    ca->epoch_rtt_us = in->rtt_us;
    ca->epoch_cwnd = cwnd;
    ca->epoch_mss = in->mss;
    /* Wait at least one starting RTT for feedback, with a 100-ms floor. */
    if (in->rtt_us > RLA_MIN_EPOCH_US) {
        ca->epoch_duration_us = in->rtt_us;
    }
    else {
        ca->epoch_duration_us = RLA_MIN_EPOCH_US;
    }
    ca->epoch_valid = true;
} /* rla_begin_epoch() */

/**
 * @brief Choose a window update for a normal ACK outside native recovery.
 * @param ca Per-connection history, updated as measurements/epochs advance.
 * @param in Current socket measurements and Linux's window-limited indication.
 * @return Window, threshold, and the reason for the chosen update.
 *
 * Delay backoff takes priority over startup or additive growth. Startup is
 * ACK-driven; after startup, additive growth is limited to one segment per
 * completed epoch and requires both low delay and adequate utilization.
 */
static inline struct rla_decision rla_on_ack(struct rla_state *ca,
                                             const struct rla_input *in)
{
    /* Holding is the default when no growth/backoff condition applies. */
    struct rla_decision out = {in->cwnd, in->ssthresh, RLA_HOLD};
    bool due = false;
    bool busy = false;
    u64 next = 0;

    /* Ignore zero RTTs: zero is unknown, not a propagation-time sample. */
    if ((in->rtt_us != 0) &&
        ((ca->min_rtt_us == 0) || (in->rtt_us < ca->min_rtt_us))) {
        ca->min_rtt_us = in->rtt_us;
    }
    if ((in->rtt_us == 0) || (in->mss == 0) ||
        (in->cwnd == 0) || (in->clamp == 0)) {
        /* Do not grow or back off using incomplete measurements. */
        rla_reset_epoch(ca);
        return out;
    }
    if ((ca->epoch_valid == true) &&
        ((in->now_us < ca->epoch_us) || (in->bytes_acked < ca->epoch_bytes))) {
        /* Rebaseline first; this avoids unsigned counter underflow. */
        rla_begin_epoch(ca, in, in->cwnd);
        return out;
    }
    if (ca->epoch_valid == false) {
        rla_begin_epoch(ca, in, in->cwnd);
    }
    else if (in->now_us - ca->epoch_us >= ca->epoch_duration_us) {
        /* Use actual elapsed time, not the nominal epoch duration. */
        due = true;
        busy = rla_busy(ca, in->bytes_acked - ca->epoch_bytes,
                        in->now_us - ca->epoch_us);
    }

    if ((due == true) && ((u64)in->rtt_us * 100 > (u64)ca->min_rtt_us * 125)) {
        /*
         * RTT > 125% of baseline suggests queue growth. Cross-products make
         * the strict threshold exact without floating point or division.
         */
        next = (u64)in->cwnd * 9 / 10;
        if (next < RLA_MIN_CWND) {
            next = RLA_MIN_CWND;
        }
        if (next > in->clamp) {
            out.cwnd = in->clamp;
        }
        else {
            out.cwnd = (u32)next;
        }
        /* End slow start so it cannot undo this backoff. */
        out.ssthresh = out.cwnd;
        out.action = RLA_DELAY;
    }
    else if ((in->cwnd < in->ssthresh) && (in->cwnd_limited == true)) {
        /*
         * Standard slow start: min(cwnd + newly ACKed packets,
         * ssthresh, clamp). Grow on eligible ACKs, not just epoch boundaries,
         * so startup can discover capacity quickly. Widen before addition
         * to avoid overflow, then cap before narrowing back to u32.
         */
        next = (u64)in->cwnd + in->acked;
        if (next > in->ssthresh) {
            next = in->ssthresh;
        }
        if (next > in->clamp) {
            out.cwnd = in->clamp;
        }
        else {
            out.cwnd = (u32)next;
        }
        out.action = RLA_STARTUP;
    }
    else if ((due == true) && (in->cwnd_limited == true) && (busy == true) &&
             ((u64)in->rtt_us * 100 < (u64)ca->min_rtt_us * 110)) {
        /*
         * Probe only below 110% of baseline, when the old window is used.
         * The 10%-25% gap creates a hold band to reduce small oscillations.
         */
        next = (u64)in->cwnd + 1;
        if (next > in->clamp) {
            out.cwnd = in->clamp;
        }
        else {
            out.cwnd = (u32)next;
        }
        out.action = RLA_ADD;
    }
    /*
     * Start from now and the resulting window; never replay missed epochs as
     * several instant increases/decreases after one delayed callback.
     */
    if (due == true) {
        rla_begin_epoch(ca, in, out.cwnd);
    }
    return out;
} /* rla_on_ack() */

/**
 * @brief Initialize RLA's private history when Linux initializes this
 * controller.
 * @param sk TCP socket using RLA.
 */
static void rla_init(struct sock *sk)
{
    struct rla_state *ca = inet_csk_ca(sk);

    memset(ca, 0, sizeof(*ca));
    /* Do not override the route/kernel's initial window or ssthresh. */
} /* rla_init() */

/**
 * @brief Supply a slow-start threshold when Linux requests congestion backoff.
 * @param sk Affected TCP socket.
 * @return Half the current window, with a minimum threshold of two segments.
 *
 * Linux decides when to request this threshold and how recovery applies it.
 * Do not also halve cwnd here or poll retransmissions for another reduction.
 * This callback can also serve native ECN congestion responses.
 */
static u32 rla_ssthresh(struct sock *sk)
{
    rla_reset_epoch(inet_csk_ca(sk));
    return rla_loss_window(tcp_snd_cwnd(tcp_sk(sk)));
} /* rla_ssthresh() */

/**
 * @brief Let Linux restore the window after detecting spurious congestion.
 * @param sk Recovering TCP socket.
 * @return The larger of the current window and Linux's saved prior window.
 */
static u32 rla_undo_cwnd(struct sock *sk)
{
    rla_reset_epoch(inet_csk_ca(sk));
    return tcp_reno_undo_cwnd(sk);
} /* rla_undo_cwnd() */

/**
 * @brief Invalidate epochs on entry to and exit from native recovery states.
 * @param sk TCP socket whose state is changing.
 * @param state New congestion-control state, not yet installed in the socket.
 */
static void rla_set_state(struct sock *sk, u8 state)
{
    /* Called before Linux updates ca_state. Also reset on recovery exit. */
    /* States from CWR onward include ECN reduction, fast recovery, and loss. */
    if ((state >= TCP_CA_CWR) ||
        (inet_csk(sk)->icsk_ca_state >= TCP_CA_CWR)) {
        rla_reset_epoch(inet_csk_ca(sk));
    }
} /* rla_set_state() */

/**
 * @brief Handle an idle restart without reusing pre-idle throughput samples.
 * @param sk TCP socket receiving the event.
 * @param event Native TCP congestion-window event.
 */
static void rla_cwnd_event(struct sock *sk, enum tcp_ca_event event)
{
    if (event == CA_EVENT_CWND_RESTART) {
        rla_reset_epoch(inet_csk_ca(sk));
    }
} /* rla_cwnd_event() */

/**
 * @brief Bridge Linux ACK processing to RLA's normal window-update rules.
 * @param sk TCP data socket whose congestion window is being updated.
 * @param ack Acknowledgment sequence number; passed on to native RTO restart.
 * @param acked Newly acknowledged/delivered segments supplied by Linux.
 *
 * Linux calls this when its congestion-control state permits the callback.
 * Normal decisions read cumulative ACKed bytes for goodput; @p acked is used
 * separately for ACK-driven slow start. Neither is a count of send() calls.
 */
static void rla_cong_avoid(struct sock *sk, u32 ack, u32 acked)
{
    struct tcp_sock *tp = tcp_sk(sk);
    struct rla_state *ca = inet_csk_ca(sk);
    struct rla_decision out = {0, 0, RLA_HOLD};
    struct rla_input in = {
        .now_us = tp->tcp_mstamp,
        .bytes_acked = tp->bytes_acked,
        .rtt_us = tp->srtt_us >> 3,
        .cwnd = tcp_snd_cwnd(tp),
        .mss = tp->mss_cache,
        .ssthresh = tp->snd_ssthresh,
        .clamp = tp->snd_cwnd_clamp,
        .acked = acked,
        .cwnd_limited = tcp_is_cwnd_limited(sk)
    };

    if (inet_csk(sk)->icsk_ca_state >= TCP_CA_CWR) {
        rla_reset_epoch(ca);
        /*
         * Native Reno-style restart after RTO; never apply delay/growth
         * rules to recovery traffic. PRR owns CWR/fast recovery.
         */
        if (inet_csk(sk)->icsk_ca_state == TCP_CA_Loss) {
            tcp_reno_cong_avoid(sk, ack, acked);
        }
        return;
    }
    /*
     * tcp_mstamp and decoded SRTT are both in microseconds. Linux stores SRTT
     * multiplied by eight, hence the shift. cwnd is segments; MSS is bytes.
     */
    out = rla_on_ack(ca, &in);
    /*
     * Only the callback writes TCP's live window; the decision helper updates
     * RLA's history and returns values, without sending packets itself.
     */
    tcp_snd_cwnd_set(tp, out.cwnd);
    tp->snd_ssthresh = out.ssthresh;
    /* Discard old native additive-increase credits after our delay decrease. */
    if (out.action == RLA_DELAY) {
        tp->snd_cwnd_cnt = 0;
    }
} /* rla_cong_avoid() */

/** @brief Linux callback table exposed under the selectable name "rla". */
static struct tcp_congestion_ops tcp_rla __read_mostly = {
    .init = rla_init,
    .ssthresh = rla_ssthresh,
    .undo_cwnd = rla_undo_cwnd,
    .set_state = rla_set_state,
    .cwnd_event = rla_cwnd_event,
    .cong_avoid = rla_cong_avoid,
    /* Keep the module referenced while sockets use it. */
    .owner = THIS_MODULE,
    .name = "rla",
    /* Allow unprivileged per-socket selection. */
    .flags = TCP_CONG_NON_RESTRICTED
};

/**
 * @brief Register the congestion controller when the module is loaded.
 * @return Zero on success, or the error returned by Linux's registration API.
 */
static int __init rla_register(void)
{
    /* History lives in a fixed-size area of each socket, not on the heap. */
    BUILD_BUG_ON(sizeof(struct rla_state) > ICSK_CA_PRIV_SIZE);
    return tcp_register_congestion_control(&tcp_rla);
} /* rla_register() */

/** @brief Remove the controller from Linux's registry on module unload. */
static void __exit rla_unregister(void)
{
    tcp_unregister_congestion_control(&tcp_rla);
} /* rla_unregister() */

module_init(rla_register);
module_exit(rla_unregister);
MODULE_AUTHOR("CS422 Fall 2026 project team");
MODULE_DESCRIPTION("RTT-Loss AIMD with throughput-gated additive probing");
MODULE_VERSION("1.0");
MODULE_LICENSE("GPL");
MODULE_ALIAS("tcp_congestion_control-rla");
