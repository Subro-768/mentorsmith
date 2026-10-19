---
id: 04-functions
title: Functions, Call Stacks & ABI Standards
order: 4
lesson_id: 04-functions
summary: System V AMD64 calling convention, stack frame layout, and return mechanisms.
tags: functions, callstack, abi, registers
---

# 4. Functions, Call Stacks & ABI Standards

### System V AMD64 Calling Convention
On 64-bit Linux:
- The first 6 integer/pointer arguments are passed directly in CPU registers:
  `%rdi`, `%rsi`, `%rdx`, `%rcx`, `%r8`, `%r9`.
- Floating-point arguments are passed in `%xmm0` through `%xmm7`.
- Additional arguments are pushed onto the stack in reverse order.
- Return values are returned in `%rax`.
