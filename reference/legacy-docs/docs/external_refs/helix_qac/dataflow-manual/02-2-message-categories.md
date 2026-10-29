# 2 | Message Categories

2 | Message Categories
In the previous chapter, various classes of problem which dataflow analysis may identify were listed:
1. Invariant operations
2. Redundant operations
3. Control flow analysis
4. Initialization tracking
5. Value tracking
6. Pointer attribute tracking
Items 4, 5 and 6 in this list characterize issues which cannot be satisfactorily described in a single message. A particular
issue has to be addressed by a family of related messages in order to clarify the context in which the diagnostic is being
generated. In DF^2, five terms are used in a special sense to distinguish these contexts.
n Constant
n Definite
n Apparent
n Suspicious
n Possible
Constant Messages
Strictly speaking, a constant message is not a dataflow analysis message at all. It identifies an issue which can be
deduced without analysis of either control flow or the run-time status of variables. For example:
void foo (void)
{
int buf[25] = {0};
...
    buf[100] = 0;
/* Message 2840 */
}
An array bounds violation in this code is identified because the array subscript value is a constant expression and it can
be deduced that the assignment operation addresses an array element outside the declared bounds of the array. The
problem would be identified as follows:
2840: Constant: Dereference of an invalid pointer value.
Definite Messages
A definite message simply identifies an issue which will definitely occur. For example:
Page 10


---
*Page 10*

void f1 (unsigned int n)
{
int buf[10] = {0};
if (n > 10)
{
        buf[n] = 100;
/* Message 2841 */
}
}
Perhaps the programmer used a ’>’ operator by mistake instead of a ’<’ in the ’if ’ statement. The result of this mistake
is, of course, an array bounds violation; the value 100 will be assigned to an element which is outside the bounds of the
array. This problem would be identified as follows:
2841: Definite: Dereference of an invalid pointer value.
Another example:
void f2 (void)
{
int buf[10];
int *p;
    p = buf;
...
    p[100] = 0;
/* Message 2841 */
}
In this code, the array bounds violation occurs indirectly through a pointer. Dataflow analysis of the code determines that
the size of the object addressed by the pointer ’p’ and deduces that the array subscript operation will result in the
dereferencing of an invalid pointer value.
A definite message does not imply that the issue will occur every time the statement is executed (e.g. on every iteration
of a loop), but it will definitely occur if the statement is ever reachable. For example, a definite array bounds violation
message may be generated in the context of a loop even though the violation may not occur in every iteration (also see
Page 11


---
*Page 11*

Modeling Limitations). For example:
void f3 (void)
{
int buf[10];
int i;
for (i = 0; i <= 10; ++i)
{
        buf[i] = i;
/* Message 2841 */
}
}
2841: Definite: Dereference of an invalid pointer value.
Apparent Messages
An apparent message identifies an issue that will occur unless a specific path elsewhere in the code, associated with an
’if ’ or ’switch’ statement or a conditional operation (? :) is always bypassed. In other words, if the issue identified by the
apparent message is not to occur then there must be a redundant path elsewhere. Consider the following example.
The code exhibits an anomaly: the code controlled by the ’if ’ statement is only reachable if the value of ’n’ is greater than
or equal to 10, and if this happens, an array bounds violation will occur when referencing ’buf[n]’.
void f1 (unsigned int n)
{
int buf[10];
if (n >= 10)
/* Redundant path ? */
{
...
/* n is not modified */
}
Page 12


---
*Page 12*

...
    buf[n] = 100;
/* Message 2842 */
}
There is therefore either an array bounds problem or a redundant path. The following message will be generated:
2842: Apparent: Dereference of an invalid pointer value.
The same message will be generated if the relational operator is changed as shown below, because a redundant path
still exists.
void f2 (unsigned int n)
{
int buf[10];
if (n < 10)
/* Redundant path ? */
{
...
/* n is not modified */
}
...
    buf[n] = 100;
/* Message 2842 */
}
In each of the above examples, the code can be seen to reflect 2 contradictory assumptions:
n Implicit in the ’if ’ statement is the assumption that the function parameter ’n’ will sometimes have a value
greater than or equal to 10. If this assumption is not true, the ’if ’ statement is effectively redundant and we
have a redundant path.
n Implicit in the array subscript operation is the assumption that the value of ’n’ must always be less than 10. If this
assumption is not true, the array subscript operation will result in an array bounds violation.
There is therefore an array bounds problem UNLESS the ’if ’ statement gives rise to a redundant path. Both the
above examples illustrate instances of what may be described as ’regular apparent’ conditions. There are other
similar situations which exhibit the same anomaly but where the array reference precedes the possible redundant path
condition. These are described as ’reverse apparent’ conditions.
Page 13


---
*Page 13*

void f3 (unsigned int n)
{
int buf[10];
    buf[n] = 100;
/* Message 2842 */
...
if (n < 10)
/* Redundant path ? */
{
...
}
}
Suspicious Messages
A suspicious message identifies an issue that will occur if certain conditions are not fulfilled in the execution of a loop
construct.
Notice that apparent and suspicious messages both identify issues associated with the use of paths. However,
n An apparent message reports that the dataflow issue will occur unless a path elsewhere is redundant, i.e. it is
never executed.
n A suspicious message identifies assumptions which are implied in a loop construct if a problem is to be avoided.
For example, avoidance of the problem may rest on assumptions such as:
a. The loop is always executed at least once
b. A certain path through the loop is always executed at least once
c. A certain path through the loop is always executed on the final iteration
Suspicious messages are therefore informational in nature and are less specific than apparent messages. They do not
necessarily identify that a real problem exists but merely attempt to expose assumptions that may have been made
unwittingly.
Consider two examples which both generate message 2843:
2843: Suspicious: Dereference of an invalid pointer value.
Example 1
An array bounds violation will occur unless:
a. the loop is entered, and
b. the ’AAA’ statement is executed in at least one iteration of the loop.
Page 14


---
*Page 14*

void path_never_executed (int i)
{
int array[5];
int j = 10;
int k;
for (k = 0; k < 10; ++k)
{
if (i > k)
{
            j = 0;
/* AAA */
}
}
    array[j] = 0;
/* Message 2843 */
}
Example 2
An array bounds violation will occur unless:
a. the loop is entered, and
b. the ’AAA’ statement is executed in the final iteration of the loop.
void path_executed_on_last_iter (int i)
{
int array[5];
int j;
int k;
Page 15


---
*Page 15*

for (k = 0; k < 10; ++k)
{
if (i > k)
{
            j = 10;
}
else
{
            j = 0;
/* AAA */
}
}
    array[j] = 0;
/* Message 2843 */
}
Possible Messages
A possible message identifies issues about which there is complete uncertainty, either because of the limitations of the
dataflow analysis engine or because the code is not written in a way which allows a more definitive conclusion to be
drawn. In practice, unless code is developed defensively with a high degree of discipline, possible messages will be
encountered frequently. ’Possible’ messages are not implemented for all dataflow conditions because their usefulness
would be very limited. Consider the following:
int foo (unsigned int n)
{
return 1000 / n; /* Message 2834 */
}
Because the value of the function parameter ’n’ on entry is considered to be unknown, DF^2 will generate message
2834 to indicate that the divisor could be zero.
2834: Possible: Division by zero.
Page 16


---
*Page 16*

Note:
If function ’foo’ is ever called within the same translation unit with argument 0, a definite message will
also be generated on the same line, with suitable sub-messages to indicate why the condition arises.
2831: Definite: Division by zero.
Page 17


---
*Page 17*
