# 1 | Introduction

1 | Introduction
Terminology
The term "dataflow analysis" refers to a range of techniques in which static analysis of source code is used to analyze
run-time behavior of a program. Dataflow analysis can identify a class of problems which may range from serious issues
such as undefined behavior to conditions which are of interest simply because they are frequently associated with coding
errors.
DF^2 is a dataflow analysis engine which functions as an integral component of Helix QAC static analysis. It identifies
some of the following conditions:
Invariant Operations
n Invariant logical operations
n Invariant controlling expressions in loop statements and ’if ’ statements
See Dataflow Terminology Notes
Redundant Operations
n Redundant initializations
n Redundant assignments
n Redundant arithmetic operations
See Dataflow Terminology Notes
Control Flow Analysis
n Unreachable code
n Infinite loops
n Executing an implicit return statement in a function with non-void return type
Initialization Tracking
n Using the value of unset data
n Passing the address of unset data to a function parameter defined as a "pointer to const type"
Value Tracking
n Division by zero
n Arithmetic operations on signed data resulting in overflow.
n Arithmetic operations on unsigned data resulting in wraparound.
n Converting a value to a signed type in which it is not representable.
n Converting a negative value to an unsigned type.
n Converting a positive value to an unsigned type in which the value is not representable.
n Performing a left shift operation on unsigned data resulting in truncation of bits.
n Performing a left shift operation on signed data resulting in an implementation defined value.
Page 6


---
*Page 6*

n Performing a shift operation with a right hand operand which is negative or too large.
n Assigning a negative value which requires a "two’s complement" representation.
Pointer Attribute Tracking
n Dereferencing a NULL pointer
n Performing arithmetic operations on a NULL pointer
n Computing an invalid pointer value - an array bounds violation
n Dereferencing an invalid pointer value - an array bounds violation
n Comparing or subtracting pointers that address different objects
Some of the conditions listed above can be readily identified in simple situations by conventional static code analysis.
More complex examples can only be identified when dataflow analysis is used to examine control flow and track the
status of objects at runtime.
Dataflow Terminology Notes
Note:
Invariant Operations
An expression which always evaluates as ’true’ or always evaluates as ’false’ is described as invariant. A
non-constant expression which can be identified as invariant is frequently associated with a mistake in
the logic.
Note:
Redundant Operations
If the value assigned to a variable is never used or is always overwritten before it can be used, the
operation may simply be unnecessary but may also be associated with a mistake in the logic.
Redundant arithmetic operations can be replaced by a constant or one of its operands.
Dataflow Message System
DF^2 supports the generation of more than 400 messages. These messages are numbered in the ranges 2668-2999,
3516-3599, 4701-4799, 4840-4999. They are grouped under various headings which include messages of varying
importance. The message groupings are as follows:
n Conversion to signed
n Conversion to unsigned
n Shift operations
n Overflow and wraparound
n Arrays
n Pointers
n NULL pointers
n Unset data
Page 7


---
*Page 7*

n Redundancy
n Floating point
n Threading
n Resources
n Invariant operations
n Control flow
n Dataflow Recovery1
Analysis Limitations
Dataflow analysis does not always yield a precise result. It is a technique which can consume a significant amount of
computing resources in both memory usage and processing time, and in many situations it is simply impractical to
perform an exhaustive analysis. In designing analysis algorithms it becomes necessary to apply judicious simplifications
and compromises in order to perform analysis within reasonable constraints of time and resources. In general, dataflow
analysis is likely to take considerably more time to execute than conventional static analysis.
Design compromises mean that conditions which should be identified will sometimes go unreported (’false negatives’)
and conditions which are benign may give rise to an unnecessary diagnostic (’false positives’). The effectiveness of
dataflow analysis has to be judged by a number of conflicting criteria:
n The effectiveness in identifying genuine problems (an absence of false negatives).
n The avoidance of incorrect messages (an absence of false positives).
n The speed with which analysis can be performed.
n The ease with which the root causes of a problem can be identified.
Diagnostics
When analyzing a potential problem such as dereferencing a NULL pointer, dataflow may arrive at a variety of
conclusions and wish to respond accordingly. For example:
n This pointer will always be NULL
n This pointer will never be NULL
n This pointer could be NULL - there is no way of knowing
n This pointer will sometimes be NULL (i.e. on some, but not necessarily all iterations of a loop)
n This pointer will be NULL if a particular path elsewhere is ever executed
n This pointer will be NULL if a loop construct elsewhere is ever bypassed
A particular challenge in dataflow analysis is that it is frequently impossible to confirm or dismiss a potential problem
without knowing the intentions of the programmer. Typically, dataflow may establish some form of anomaly or
contradiction is present in the code.
Such anomalies can be reported in more than one way, for example:
1Messages 275x highlight problems with the running of dataflow itself
Page 8


---
*Page 8*

1. If the particular path at location A is executed, it is certain that a NULL pointer dereference will occur at point B.
2. If a NULL pointer dereference is to be avoided at point B, the path at location A must be unreachable.
The essence of problems such as this is that we have no way of knowing exactly where the root of the problem lies.
Dataflow analysis is only able to point out that there are two potential problems and that one of them is bound to exist;
either there is a redundant path in the code or there is a NULL pointer dereference.
Dataflow analysis is a technique which has inherent limitations; there will always be runtime problems which cannot be
diagnosed simply because of a lack of sufficient information within the available source code. For example,
dereferencing a pointer which is a function parameter without first checking that the pointer is not NULL is a potential
vulnerability - but is not in itself evidence of a definite problem.
Page 9


---
*Page 9*
