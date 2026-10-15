// SPDX-License-Identifier: GPL-2.0-only
/* RLA: RTT-Loss AIMD. See Assignment2/part3b-writeup.tex for the design.
 * Linux owns ACK processing, retransmission, PRR, ECN and RTO recovery.
 */
#include <linux/build_bug.h>
#include <linux/module.h>
#include <net/tcp.h>

#include "rla_controller.h"

static void rla_init(struct sock *sk)
{
	struct rla_state *ca = inet_csk_ca(sk);

	memset(ca, 0, sizeof(*ca));
	/* Do not override the route/kernel's initial window or ssthresh. */
}

static u32 rla_ssthresh(struct sock *sk)
{
	rla_reset_epoch(inet_csk_ca(sk));
	return rla_loss_window(tcp_snd_cwnd(tcp_sk(sk)));
}

static u32 rla_undo_cwnd(struct sock *sk)
{
	rla_reset_epoch(inet_csk_ca(sk));
	return tcp_reno_undo_cwnd(sk);
}

static void rla_set_state(struct sock *sk, u8 state)
{
	/* Called before Linux updates ca_state. Also reset on recovery exit. */
	if (state >= TCP_CA_CWR || inet_csk(sk)->icsk_ca_state >= TCP_CA_CWR)
		rla_reset_epoch(inet_csk_ca(sk));
}

static void rla_cwnd_event(struct sock *sk, enum tcp_ca_event event)
{
	if (event == CA_EVENT_CWND_RESTART)
		rla_reset_epoch(inet_csk_ca(sk));
}

static void rla_cong_avoid(struct sock *sk, u32 ack, u32 acked)
{
	struct tcp_sock *tp = tcp_sk(sk);
	struct rla_state *ca = inet_csk_ca(sk);
	struct rla_decision out;
	struct rla_input in;

	if (inet_csk(sk)->icsk_ca_state >= TCP_CA_CWR) {
		rla_reset_epoch(ca);
		/* Native Reno-style restart after RTO; never apply delay/growth
		 * rules to recovery traffic. PRR owns CWR/fast recovery.
		 */
		if (inet_csk(sk)->icsk_ca_state == TCP_CA_Loss)
			tcp_reno_cong_avoid(sk, ack, acked);
		return;
	}
	in = (struct rla_input) {
		.now_us = tp->tcp_mstamp,
		.bytes_acked = tp->bytes_acked,
		.rtt_us = tp->srtt_us >> 3,
		.cwnd = tcp_snd_cwnd(tp),
		.mss = tp->mss_cache,
		.ssthresh = tp->snd_ssthresh,
		.clamp = tp->snd_cwnd_clamp,
		.acked = acked,
		.cwnd_limited = tcp_is_cwnd_limited(sk),
	};
	out = rla_on_ack(ca, &in);
	tcp_snd_cwnd_set(tp, out.cwnd);
	tp->snd_ssthresh = out.ssthresh;
	if (out.action == RLA_DELAY)
		tp->snd_cwnd_cnt = 0;
}

static struct tcp_congestion_ops tcp_rla __read_mostly = {
	.init = rla_init,
	.ssthresh = rla_ssthresh,
	.undo_cwnd = rla_undo_cwnd,
	.set_state = rla_set_state,
	.cwnd_event = rla_cwnd_event,
	.cong_avoid = rla_cong_avoid,
	.owner = THIS_MODULE,
	.name = "rla",
	.flags = TCP_CONG_NON_RESTRICTED,
};

static int __init rla_register(void)
{
	BUILD_BUG_ON(sizeof(struct rla_state) > ICSK_CA_PRIV_SIZE);
	return tcp_register_congestion_control(&tcp_rla);
}

static void __exit rla_unregister(void)
{
	tcp_unregister_congestion_control(&tcp_rla);
}

module_init(rla_register);
module_exit(rla_unregister);
MODULE_AUTHOR("CS422 Fall 2026 project team");
MODULE_DESCRIPTION("RTT-Loss AIMD with throughput-gated additive probing");
MODULE_VERSION("1.0");
MODULE_LICENSE("GPL");
MODULE_ALIAS("tcp_congestion_control-rla");
