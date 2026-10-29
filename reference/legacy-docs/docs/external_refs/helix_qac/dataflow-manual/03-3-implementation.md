# 3 | Implementation

3 | Implementation
Solver Technology
DF^2 employs an Satisfiability Modulo Theories (SMT) solver1 engine to model the status of objects at run time. Code
statements which impose constraints on the value of variables are translated into a series of assertions which are
supplied to the solver. The solver is interrogated with queries in order to identify conditions which need to be reported.
Variable Interdependency
The power of a solver engine in dataflow analysis is that it is able to provide an accurate model of the values of variables
throughout the execution of a function and also model the relationships which exist between variables.
void foo (int i)
{
int * p = (i > 0) ? (int *)0x1234 : 0;
/* ... */
/* p can be NULL here */
if (i > 10)
{
*p = 1;
/* p is never NULL here */
}
}
Wraparound and Overflow
One aspect of solver technology which can cause some confusion is that it may sometimes arrive at conclusions which
are theoretically correct but which seem at first sight to be unreasonable. Consider a trivial example. It might appear that
the control expression in the first ’if ’ statement shown below will only be ’true’ if x has a value of 2U. We might therefore
expect that the control expression in the second ’if ’ statement should be identified as invariant - i.e. always ’true’. In fact
this is not so, and instead we find that message 2912 is generated on the first ’if ’ statement:
void f1 (unsigned int x)
1Uses Yices™decision procedures technology under license from SRI International ®
Page 18


---
*Page 18*

{
if ((x * 2U) == 4U) /* 2912 */
{
if (x == 2U) /* */
{
}
}
}
2912: Apparent: Wraparound in unsigned arithmetic operation.
The solver determines that there are 2 possible values of ’x’ which satisfy the first equality operation; 2U is the most
obvious, but because unsigned wraparound may occur in the multiplication operation, a value of 32770U is also a
possible solution (assuming a 16 bit integer implementation).
Message 2912 is generated because an ’apparent’ anomaly is identified. Either there is an unreachable path issue or a
wraparound issue. Either we have a situation where ’x’ is always equal to 2U (which results in an unreachable path), or
else wraparound must occur in the first ’if ’ expression when ’x’ is multiplied by 2U.
A similar situation arises with signed arithmetic but overflow is identified rather than wraparound.
void f2 (signed int x)
{
if ((x * 2) == 4)
/* 2802 */
{
if (x == 2)
/* */
{
}
}
}
2802: Apparent: Overflow in signed arithmetic operation.
Variable Tracking
A primary function of dataflow analysis is tracking the value, status and attributes of objects at run-time. Five forms of
tracking are recognized:
Page 19


---
*Page 19*

Initilization Tracking
The initialization status of local automatic objects is tracked in order to identify any attempt to use an ’unset’ value.
Value Tracking
Tracking of arithmetic values is implemented for objects of integer or pointer type.
Pointer Attribute tracking
Various attributes associated with an object of pointer type are tracked:
n a unique object identifier
n the size of the object into which the pointer is pointing
n the offset within that object to which the pointer is pointing
These attributes are used to identify
a. whether two pointers address the same object
b. when pointer arithmetic results in the generation of an invalid pointer
c. when an attempt is made to dereference an address outside the bounds of an object
Pointer Aliasing
When an address of an object with integer, class, struct or union type is assigned to a pointer, or such a pointer is
assigned to another pointer, the value of pointer dereference (object pointed to) is modeled and tracking functions
described above are applied to it.
Inter-function Analysis
When an argument is passed to a function its value is bound to the corresponding parameter. Additionally, for a pointer
parameter, the value of pointer dereference of argument is propagated to that of parameter. Similarly, the value
(including pointer dereference) is propagated from return expression to call site.
Objects of Scalar type
n Initialization tracking is implemented for automatic objects of any scalar type.
n Value tracking is implemented for objects of all integer types (so floating types are excluded).
n Pointer attribute tracking and pointer aliasing are implemented for objects of pointer type.
Objects of Aggregate Type
n Arrays
Value tracking is implemented for individual elements of an array of type:
l integer type
l pointer to non-array type (for the purposes of pointer attribute tracking)
l union without aggregate members
when they are indexed with a constant expression or an expression with a unique value determined by dataflow.
For the purposes of initialization tracking, an array is treated as a single discrete object. If one element of a
local automatic array is initialized, DF^2 assumes that the whole array is initialized.
Page 20


---
*Page 20*

n Struct and class
Value tracking, initialization tracking and pointer tracking/aliasing are implemented for each member of a
struct
Objects of Union Type
In order to track the behavior of individual union members correctly, it would be necessary to provide a faithful model of
the storage of each member with an accurate representation of several aspects of behavior which are implementation-
defined. DF^2 assumes a little-endian memory model with type sizes and alignments which reflect settings of the
configuration options: -size and -align. Within the assumptions of this model, the value of one member will reflect values
assigned to another member; however it must also be remembered that DF^2 will not track the value of any member of
array type.
union U
{
unsigned int ui;
struct S
{
unsigned short s1;
unsigned short s2;
} s;
};
void foo (void)
{
union U u = { 0x00020001 };
if (u.s.s1 == 1) { }
/* 2995 & 2991 */
if (u.s.s2 == 2) { }
/* 2995 & 2991 */
}
2995: The result of this logical operation is always ’true’.
2991: The value of this ’if’ controlling expression is always true.
Volatile Objects
volatile objects or members cannot modeled, as their value can change on every access.
Page 21


---
*Page 21*

API Usage Checker
Function Arguments
DF^2 performs analysis on the arguments to some functions defined in the C Standard Library to identify issues such as:
n an invalid NULL pointer argument
n a pointer argument which addresses an array which is of insufficient length
n the maximum number of characters to be written is larger than the target buffer size
n a copy operation being performed on overlapping objects
Such issues, which would normally result in undefined behavior inside the function, are identified with corresponding
dataflow messages at the location of the function call. For example, the argument in a call to ’atof’ cannot be a NULL
pointer:
#include <stdlib.h>
void f1 (void)
{
char * c = NULL;
atof (c);
/* Message 2811 */
}
2811: Definite: Dereference of NULL pointer.
The third parameter in a call to strncpy should not be larger than the size of the buffer specified as the first parameter:
void f2 (char * src)
{
char dst[10];
    size_t size = 20U;
strncpy (dst, src, size);
/* Message 2846 */
}
2846: Definite: Maximum number of characters to be written is larger than the target buffer size.
Even if the actual size of the source buffer is small enough to fit in the destination buffer, message 2846 will still be issued
(despite strncpy safely stopping copying characters when it reaches the null terminator in src) - there is still a mismatch
between the destination buffer and number of bytes to copy.
Other standard library functions that accept a destination buffer are checked, for example:
Page 22


---
*Page 22*

void f3(void)
{
char buf[10];
sprintf(buf, "1234567890");
/* Message 2840 */
strcpy(buf, "1234567890");
/* Message 2840 */
}
2840: Constant: Dereference of an invalid pointer value.
Function return Values
Analysis can also use known characteristics of a Standard Library function when the return value is subsequently used.
For example:
n malloc always returns either NULL, or a suitably sized buffer of bytes
n strchr always returns either NULL, or a pointer to an element within the array addressed by the first argument
#include <stdlib.h>
void f2 (void)
{
int * m = (int *) malloc(3 * sizeof(int));
if (m != NULL)
{
        m[3] = 0; /* Message 2841 */
}
}
2841: Definite: Dereference of an invalid pointer value.
Modeling Limitations
There are a number of specific aspects in dataflow analysis which may give rise to ’false positives’ and ’false negatives’.
Inter-function Analysis
DF^2 performs dataflow analysis including modeling of function calls between translation units where function definitions
have previously been analyzed.
Page 23


---
*Page 23*

See Inter-TU Analysis for more information.
Loops
Loops typically modify one or more variables but, depending on the complexity of the loop, it is generally impractical to
track the values of every variable through every iteration. A loop variable is defined as any variable that is modified within
the loop. The value of a loop variable is analyzed in three contexts:
n the value in the first iteration
n the value in any intermediate iteration
n the value in the last iteration
If DF^2 finds an issue, sub-message 1571 is used to identify whether it occurs in the first, intermediate or last iteration.
For example:
void loop (void)
{
int i;
for (i = 0; i < 10; ++i)
{
1 / i;
/* Message 2831 - first iteration */
1 / (i - 3);
/* Message 2831 - intermediate iteration */
1 / (i - 9);
/* Message 2831 - last iteration */
}
1 / (i - 10);
/* Message 2831 */
}
2831: Definite: Division by zero.
Variables with Unknown Value
The status of a variable often has to be classified as ’unknown’ - meaning that no relevant information is available by
which its value or its attributes may be determined. This is the status, for example, of
n function parameters on entry to a function
n global variables on entry to a function
n variable assigned the result of a function call
Page 24


---
*Page 24*

unless the function's body can be expanded into the caller (the definition is available to DF^2, it’s not indirectly recursive
or too large for the supplied -po df:inter option, see Dataflow Component Configuration). It is particularly difficult to track
the status of a global variable because of the uncertainty introduced whenever another function is called. Whereas, local
variables can be monitored with relative confidence, tracking a global variable is often a far more complex task. DF^2
tracks the status of a global variable within the current function, but, if a function call is encountered, its status
immediately becomes unknown, unless the function call can be expanded.
Pointer Aliasing
There are some cases where the value of a pointer dereference is not modeled in the entire function body:
n the pointer is involved in any pointer arithmetic on the right hand side of initialization or assignment
n the pointer is assigned the result of an (implicit) pointer cast where at least one of the ’to’ or ’from’ types is a
pointer to void, struct or union, or the ’to’ type is a pointer to a type with a smaller value range than that for the
’from’ type
n the pointer is assigned another pointer that is not modeled
n the pointer is passed as an argument to a parameter that is not modeled
Page 25


---
*Page 25*
