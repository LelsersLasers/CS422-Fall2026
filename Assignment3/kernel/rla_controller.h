/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef RLA_CONTROLLER_H
#define RLA_CONTROLLER_H

/* The module and host-side tests execute this same integer controller. */
#ifdef __KERNEL__
#include <linux/types.h>
#else
#include <stdbool.h>
#include <stdint.h>
typedef uint32_t u32;
typedef uint64_t u64;
#endif

#define RLA_MIN_EPOCH_US 100000U
#define RLA_MIN_CWND 2U

struct rla_state {
	u64 epoch_us;
	u64 epoch_bytes;
	u32 min_rtt_us;
	u32 epoch_rtt_us;
	u32 epoch_cwnd;
	u32 epoch_mss;
	u32 epoch_duration_us;
	bool epoch_valid;
};

struct rla_input {
	u64 now_us;
	u64 bytes_acked;
	u32 rtt_us;
	u32 cwnd;
	u32 mss;
	u32 ssthresh;
	u32 clamp;
	u32 acked;
	bool cwnd_limited;
};

enum rla_action { RLA_HOLD, RLA_STARTUP, RLA_ADD, RLA_DELAY };

struct rla_decision {
	u32 cwnd;
	u32 ssthresh;
	enum rla_action action;
};

static inline u32 rla_loss_window(u32 cwnd)
{
	return cwnd / 2 < RLA_MIN_CWND ? RLA_MIN_CWND : cwnd / 2;
}

static inline void rla_reset_epoch(struct rla_state *ca)
{
	/* Preserve the lifetime minimum; discard an idle/recovery-mixed epoch. */
	ca->epoch_valid = false;
}

static inline bool rla_multiply(u64 a, u64 b, u64 *out)
{
	if (b && a > (~(u64)0) / b)
		return false;
	*out = a * b;
	return true;
}

static inline bool rla_busy(const struct rla_state *ca, u64 bytes, u64 dt)
{
	u64 lhs, rhs;

	/* G/(W0*MSS0/R0) >= 4/5; factors of 8 and 1e6 cancel.
	 * Overflow means "not enough trustworthy evidence to grow".
	 */
	return rla_multiply(bytes, ca->epoch_rtt_us, &lhs) &&
	       rla_multiply(lhs, 5, &lhs) &&
	       rla_multiply(dt, ca->epoch_cwnd, &rhs) &&
	       rla_multiply(rhs, ca->epoch_mss, &rhs) &&
	       rla_multiply(rhs, 4, &rhs) && lhs >= rhs;
}

static inline void rla_begin_epoch(struct rla_state *ca,
				   const struct rla_input *in, u32 cwnd)
{
	ca->epoch_us = in->now_us;
	ca->epoch_bytes = in->bytes_acked;
	ca->epoch_rtt_us = in->rtt_us;
	ca->epoch_cwnd = cwnd;
	ca->epoch_mss = in->mss;
	ca->epoch_duration_us = in->rtt_us > RLA_MIN_EPOCH_US ?
		in->rtt_us : RLA_MIN_EPOCH_US;
	ca->epoch_valid = true;
}

static inline struct rla_decision rla_on_ack(struct rla_state *ca,
					    const struct rla_input *in)
{
	struct rla_decision out = { in->cwnd, in->ssthresh, RLA_HOLD };
	bool due = false;
	bool busy = false;
	u64 next;

	if (in->rtt_us && (!ca->min_rtt_us || in->rtt_us < ca->min_rtt_us))
		ca->min_rtt_us = in->rtt_us;
	if (!in->rtt_us || !in->mss || !in->cwnd || !in->clamp) {
		rla_reset_epoch(ca);
		return out;
	}
	if (ca->epoch_valid && (in->now_us < ca->epoch_us ||
				in->bytes_acked < ca->epoch_bytes)) {
		rla_begin_epoch(ca, in, in->cwnd);
		return out;
	}
	if (!ca->epoch_valid)
		rla_begin_epoch(ca, in, in->cwnd);
	else if (in->now_us - ca->epoch_us >= ca->epoch_duration_us) {
		due = true;
		busy = rla_busy(ca, in->bytes_acked - ca->epoch_bytes,
				in->now_us - ca->epoch_us);
	}

	if (due && (u64)in->rtt_us * 100 > (u64)ca->min_rtt_us * 125) {
		next = (u64)in->cwnd * 9 / 10;
		if (next < RLA_MIN_CWND)
			next = RLA_MIN_CWND;
		out.cwnd = next > in->clamp ? in->clamp : (u32)next;
		out.ssthresh = out.cwnd;
		out.action = RLA_DELAY;
	} else if (in->cwnd < in->ssthresh && in->cwnd_limited) {
		/* Standard slow start: min(cwnd + newly ACKed packets,
		 * ssthresh, clamp). No additive credit is carried across epochs.
		 */
		next = (u64)in->cwnd + in->acked;
		if (next > in->ssthresh)
			next = in->ssthresh;
		out.cwnd = next > in->clamp ? in->clamp : (u32)next;
		out.action = RLA_STARTUP;
	} else if (due && in->cwnd_limited && busy &&
		   (u64)in->rtt_us * 100 < (u64)ca->min_rtt_us * 110) {
		next = (u64)in->cwnd + 1;
		out.cwnd = next > in->clamp ? in->clamp : (u32)next;
		out.action = RLA_ADD;
	}
	if (due)
		rla_begin_epoch(ca, in, out.cwnd);
	return out;
}

#endif
