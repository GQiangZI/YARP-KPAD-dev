/*
 * Copyright (C) 2008 The Android Open Source Project
 * SPDX-License-Identifier: Apache-2.0
 *
 * Minimal dynamic ARM64 entry for the Recovery ramdisk's Bionic.
 * Based on Android 16 libc/arch-common/bionic/crtbegin.c.
 */
#include <stddef.h>

/* The helper has no executable constructors or destructors. */
struct bionic_structors {
    void *preinit_array;
    void *init_array;
    void *fini_array;
    size_t preinit_array_count;
    size_t init_array_count;
    size_t fini_array_count;
};
extern int main(int, char **, char **);
extern _Noreturn void __libc_init(void *, void (*)(void), int (*)(int, char **, char **),
                                 const struct bionic_structors *);

__attribute__((used))
static _Noreturn void start_main(void *raw_args) {
    static const struct bionic_structors empty;
    __libc_init(raw_args, NULL, main, &empty);
}

__asm__(".text\n"
        ".global _start\n"
        ".type _start, %function\n"
        "_start:\n"
        "mov x29, xzr\n"
        "mov x30, xzr\n"
        "mov x0, sp\n"
        "b start_main\n"
        ".size _start, .-_start\n");
