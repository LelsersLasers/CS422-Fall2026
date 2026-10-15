ifneq ($(KERNELRELEASE),)
obj-m := tcp_rla.o
else
KDIR ?= /lib/modules/$(shell uname -r)/build
HOSTCC ?= cc
TEST_BINARY := /tmp/cs422-rla-controller-test

.PHONY: all clean test
all:
	$(MAKE) -C "$(KDIR)" M="$(CURDIR)" modules

clean:
	$(MAKE) -C "$(KDIR)" M="$(CURDIR)" clean

test:
	$(HOSTCC) -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -g ../tests/test_controller.c -o "$(TEST_BINARY)"
	"$(TEST_BINARY)"
endif
