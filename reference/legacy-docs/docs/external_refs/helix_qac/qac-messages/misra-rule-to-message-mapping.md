# MISRA C:2012 Rule-to-Message Mapping

Source: M3CM Component Manual (M3CM 5.6.0)

Total rules mapped: 234

| MISRA Rule | Description | Enforced By | Messages |
|------------|-------------|-------------|----------|
| Rule-9.1 | The value of an object with automatic storage duration shall not be read before it has been set | DATAFLOW | 2961, 2962, 2963, 2966, 2967, 2968, 2971, 2972, 2973 |
| Rule-9.1 | The value of an object with automatic storage duration shall not be read before it has been set | QAC | 2883 |
| Rule-12.5 | The sizeof operator shall not have an operand which is a function parameter declared as 'array of type' | QAC | 1321 |
| Rule-17.4 | All exit paths from a function with non-void return type shall have an explicit return statement with an expression | DATAFLOW | 2887, 2888 |
| Rule-17.4 | All exit paths from a function with non-void return type shall have an explicit return statement with an expression | QAC | 0745, 3113, 3114 |
| Rule-19.1 | An object shall not be assigned or copied to an overlapping object | DATAFLOW | 2776, 2777, 2778 |
| Rule-19.1 | An object shall not be assigned or copied to an overlapping object | QAC | 0681 |
| Rule-21.13 | Any value passed to a function in <ctype.h> shall be representable as an unsigned char or be the value EOF | DATAFLOW | 2796, 2797, 2798 |
| Rule-21.17 | Use of the string handling functions from <string.h> shall not result in accesses beyond the bounds of the objects referenced by their pointer paramet | DATAFLOW | 2835, 2836, 2935, 2936, 2937, 2938 |
| Rule-21.18 | The size_t argument passed to any function in <string.h> shall have an appropriate value | DATAFLOW | 2865, 2866, 2867, 2868, 4880, 4881, 4882, 4883 |
| Rule-21.19 | The pointers returned by the Standard Library functions lovaleconv, getenv, setlocale or strerror shall only be used as if they have pointer to const- | QAC | 1492, 1493, 1494, 1498 |
| Rule-21.20 | The pointer returned by the Standard Library functions asctime, ctime, gmtime, localtime, localeconv, getenv, setlocale, or strerror shall not be used | DATAFLOW | 2681, 2682, 2683 |
| Rule-22.2 | A block of memory shall only be freed if it was allocated by means of a Standard Library function | DATAFLOW | 2716, 2717, 2718, 2721, 2722, 2723 |
| Rule-22.4 | There shall be no attempt to write to a stream which has been opened as read-only | DATAFLOW | 2686, 2687, 2688 |
| Rule-22.5 | A pointer to a FILE object shall not be dereferenced | QAC | 1485, 1486 |
| Rule-22.6 | The value of a pointer to a FILE shall not be used after the associated stream has been closed | DATAFLOW | 2696, 2697, 2698 |
| Rule-22.12 | Thread objects, thread synchronization objects, and thread-specific storage pointers shall only be accessed by the appropriate Standard Library functi | QAC | 2035, 2036 |
| Rule-22.14 | Thread synchronization objects shall be initialized before being accessed | MTA | 1787, 1788 |
| Rule-22.20 | Thread-specific storage pointers shall be created before being accessed | MTA | 1785, 1786 |
| Rule-9.7 | Atomic objects shall be appropriately initialized before being accessed | DATAFLOW | 4836, 4837, 4838 |
| Rule-17.9-C11 | A function declared with a _Noreturn function specifier shall not return to its caller | DATAFLOW | 2886 |
| Rule-17.3-C90 | A function shall not be declared implicitly | QAC | 3335 |
| Rule-7.5 | The argument of an integer-constant macro shall have an appropriate form | QAC | 3185, 3186 |
| Rule-17.6 | The declaration of an array parameter shall not contain the static keyword between the [ ] | QAC | 1058 |
| Rule-18.10 | Pointers to variably-modified array types shall not be used | QAC | 1187 |
| Rule-21.22 | All operand arguments to any type-generic macros declared in <tgmath.h> shall have an appropriate essential type | QAC | 1160, 1161, 1162 |
| Rule-1.1 | The program shall contain no violations of the standard C syntax and constraints, and shall not exceed the implementation's translation limits | QAC | 0232, 0233, 0244, 0268, 0321, 0322, 0323, 0327, 0338, 0422 (+195 more) |
| Rule-1.3 | There shall be no occurrence of undefined or critical unspecified behaviour | DATAFLOW | 2726, 2727, 2728, 2731, 2732, 2733, 2746, 2747, 2748, 2801 (+25 more) |
| Rule-1.3 | There shall be no occurrence of undefined or critical unspecified behaviour | QAC | 0160, 0161, 0162, 0163, 0164, 0165, 0166, 0167, 0168, 0169 (+103 more) |
| Rule-1.3 | There shall be no occurrence of undefined or critical unspecified behaviour | RCMA | 1509, 1510 |
| Rule-2.1 | A project shall not contain unreachable code | QAC | 0594, 1460, 2744, 2880, 2882, 3219 |
| Rule-2.1 | A project shall not contain unreachable code | RCMA | 1503 |
| Rule-2.2 | A project shall not contain dead code | DATAFLOW | 2980, 2982, 2983, 2985, 2986, 2987, 2995, 2996 |
| Rule-2.2 | A project shall not contain dead code | QAC | 2995, 2996, 3110, 3112, 3404, 3422, 3423, 3424, 3425, 3426 (+1 more) |
| Rule-3.1 | The character sequences /* and // shall not be used within a comment. | QAC | 3108 |
| Rule-4.1 | Octal and hexadecimal escape sequences shall be terminated | QAC | 3636, 3637 |
| Rule-5.1 | External identifiers shall be distinct | QAC | 0777 |
| Rule-5.1 | External identifiers shall be distinct | RCMA | 1712 |
| Rule-5.2 | Identifiers declared in the same scope and name space shall be distinct | QAC | 0779 |
| Rule-5.3 | An identifier declared in an inner scope shall not hide an identifier declared in an outer scope | QAC | 0795, 2547, 3334 |
| Rule-5.4 | Macro identifiers shall be distinct | QAC | 0788, 0791, 0797, 0798 |
| Rule-5.5 | Identifiers shall be distinct from macro names | QAC | 0784, 0787 |
| Rule-5.6 | A typedef name shall be a unique identifier | RCMA | 1506, 1507, 1508 |
| Rule-5.7 | A tag name shall be a unique identifier | QAC | 2547 |
| Rule-5.7 | A tag name shall be a unique identifier | RCMA | 1750 |
| Rule-5.8 | Identifiers that define objects or functions with external linkage shall be unique | RCMA | 1525, 1526, 1756, 1758 |
| Rule-6.1 | Bit-fields shall only be declared with an appropriate type | QAC | 0634, 0635 |
| Rule-6.2 | Single-bit named bit fields shall not be of a signed type | QAC | 3660 |
| Rule-6.3 | A bit field shall not be declared as a member of a union | QAC | 3622 |
| Rule-7.1 | Octal constants shall not be used | QAC | 0336, 0339 |
| Rule-7.2 | A "u" or "U" suffix shall be applied to all integer constants that are represented in an unsigned type | QAC | 1281 |
| Rule-7.3 | The lowercase character "l" shall not be used in a literal suffix | QAC | 1280 |
| Rule-7.4 | A string literal shall not be assigned to an object unless the object's type is "pointer to const-qualified char" | QAC | 0752, 0753, 0754 |
| Rule-8.2 | Function types shall be in prototype form with named parameters | QAC | 1335, 1336, 3001, 3002, 3007 |
| Rule-8.3 | All declarations of an object or function shall use the same names and type qualifiers | QAC | 0606, 0624, 1330, 3675 |
| Rule-8.3 | All declarations of an object or function shall use the same names and type qualifiers | RCMA | 1707, 1708, 1709 |
| Rule-8.4 | A compatible declaration shall be visible when an object or function with external linkage is defined | QAC | 3331, 3408 |
| Rule-8.5 | An external object or function shall be declared once in one and only one file | QAC | 3449, 3451 |
| Rule-8.5 | An external object or function shall be declared once in one and only one file | RCMA | 1513 |
| Rule-8.6 | An identifier with external linkage shall have exactly one external definition | QAC | 0630, 3406 |
| Rule-8.6 | An identifier with external linkage shall have exactly one external definition | RCMA | 1509, 1752, 1753 |
| Rule-8.8 | The static storage class specifier shall be used in all declarations of objects and functions that have internal linkage | QAC | 3224 |
| Rule-8.12 | Within an enumerator list, the value of an implicitly-specified enumeration constant shall be unique | QAC | 0724 |
| Rule-9.2 | The initializer for an aggregate or union shall be enclosed in braces | QAC | 0692, 0693, 0694 |
| Rule-9.3 | Arrays shall not be partially initialized | QAC | 0686 |
| Rule-9.6 | An initializer using chained designators shall not contain initializers without designators | QAC | 1395 |
| Rule-10.1 | Operands shall not be of an inappropriate essential type. | QAC | 3101, 3102, 4115, 4116, 4500, 4501, 4502, 4503, 4504, 4505 (+28 more) |
| Rule-10.2 | Expressions of essentially character type shall not be used inappropriately in addition and subtraction operations | QAC | 1810, 1811, 1812, 1813, 1814 |
| Rule-10.3 | The value of an expression shall not be assigned to an object with a narrower essential type or of a different essential type category. | QAC | 0570, 0572, 1157, 1257, 1264, 1265, 1266, 1291, 1292, 1293 (+49 more) |
| Rule-10.4 | Both operands of an operator in which the usual arithmetic conversions are performed shall have the same essential type category | QAC | 1800, 1802, 1803, 1804, 1820, 1821, 1822, 1823, 1824, 1830 (+22 more) |
| Rule-10.6 | The value of a composite expression shall not be assigned to an object with wider essential type | QAC | 4490, 4491, 4492 |
| Rule-10.7 | If a composite expression is used as one operand of an operator in which the usual arithmetic conversions are performed then the other operand shall n | QAC | 1890, 1891, 1892, 1893, 1894, 1895 |
| Rule-10.8 | The value of a composite expression shall not be cast to a different essential type category or a wider essential type | QAC | 4389, 4390, 4391, 4392, 4393, 4394, 4395 |
| Rule-11.1 | Conversions shall not be performed between a pointer to a function and any other type | QAC | 0302, 0305, 0307, 0313 |
| Rule-11.2 | Conversions shall not be performed between a pointer to an incomplete type and any other type | QAC | 0308, 0323, 0324, 0325 |
| Rule-11.3 | A conversion shall not be performed between a pointer to object type and a pointer to a different object type | QAC | 0310, 3305 |
| Rule-11.6 | A cast shall not be performed between pointer to void and an arithmetic type | QAC | 0326, 0327 |
| Rule-11.7 | A cast shall not be performed between pointer to object and a non-integer arithmetic type | QAC | 0301, 0328 |
| Rule-11.8 | A cast shall not remove any const or volatile qualification from the type pointed to by a pointer | QAC | 0311, 0312 |
| Rule-11.9 | The macro NULL shall be the only permitted form of integer null pointer constant | QAC | 3003, 3004 |
| Rule-12.2 | The right hand operand of a shift operator shall lie in the range zero to one less than the width in bits of the essential type of the left hand opera | DATAFLOW | 2791, 2792, 2793, 2794 |
| Rule-12.2 | The right hand operand of a shift operator shall lie in the range zero to one less than the width in bits of the essential type of the left hand opera | QAC | 0499, 2790 |
| Rule-13.2 | The value of an expression and its persistent side-effects shall be the same under all permitted evaluation orders and shall be independent from threa | QAC | 0400, 0401, 0402, 0403, 0404, 0405, 1114, 1115, 1116 |
| Rule-13.5 | The right hand operand of a logical && or \|\| operator shall not contain persistent side effects | QAC | 3415 |
| Rule-13.6 | The operand of the sizeof operator shall not contain any expression which has potential side-effects | QAC | 0945, 3307 |
| Rule-14.1 | A loop counter shall not have essentially floating type | QAC | 3339, 3340 |
| Rule-14.2 | A for loop shall be well-formed | QAC | 2461, 2462, 2463, 2464, 2467, 2468, 2469, 2471, 2472, 2476 (+1 more) |
| Rule-14.3 | Controlling expressions shall not be invariant | DATAFLOW | 2990, 2991, 2992, 2993, 2994, 2997, 2998 |
| Rule-14.3 | Controlling expressions shall not be invariant | QAC | 2741, 2742, 2990, 2991, 2992, 2993, 2994, 2997, 2998, 3493 (+1 more) |
| Rule-14.4 | The controlling expression of an if-statement and the controlling expression of an iteration-statement shall have essentially Boolean type | QAC | 3344 |
| Rule-15.2 | The goto statement shall jump to a label declared later in the same function | QAC | 3310 |
| Rule-15.3 | Any label referenced by a goto statement shall be declared in the same block, or in any block enclosing the goto statement | QAC | 3327 |
| Rule-15.6 | The body of an iteration-statement or a selection-statement shall be a compound-statement | QAC | 2212, 2214, 2218, 2219, 3402 |
| Rule-15.7 | All if ... else if constructs shall be terminated with an else statement | QAC | 2004, 2013 |
| Rule-16.1 | All switch statements shall be well-formed | QAC | 2008, 3234 |
| Rule-16.2 | A switch label shall only be used when the most closely-enclosing compound statement is the body of a switch statement | QAC | 2019 |
| Rule-16.3 | An unconditional break statement shall terminate every switch-clause | QAC | 2003, 2020, 2023, 2024 |
| Rule-16.4 | Every switch statement shall have a default label | QAC | 2002, 2016 |
| Rule-16.5 | A default label shall appear as either the first or the last switch label of a switch statement | QAC | 2012 |
| Rule-16.6 | Every switch statement shall have at least two switch-clauses | QAC | 3315, 3353 |
| Rule-16.7 | A switch-expression shall not have essentially Boolean type | QAC | 0735 |
| Rule-17.1 | The standard header file <stdarg.h> shall not be used | M3CM | 5130, 5140 |
| Rule-17.1 | The standard header file <stdarg.h> shall not be used | QAC | 1337 |
| Rule-17.2 | Functions shall not call themselves, either directly or indirectly | QAC | 3670 |
| Rule-17.2 | Functions shall not call themselves, either directly or indirectly | RCMA | 1520 |
| Rule-17.5 | The function argument corresponding to a parameter declared to have an array type shall have an appropriate number of elements | DATAFLOW | 2781, 2782, 2783, 2784 |
| Rule-17.7 | The value returned by a function having non-void return type shall be used | QAC | 3200 |
| Rule-17.13 | A function type shall not be type qualified | QAC | 1147 |
| Rule-18.1 | A pointer resulting from arithmetic on a pointer operand shall address an element of the same array as that pointer operand | DATAFLOW | 2840, 2841, 2842, 2843, 2930, 2931, 2932, 2933, 2935, 2936 (+2 more) |
| Rule-18.1 | A pointer resulting from arithmetic on a pointer operand shall address an element of the same array as that pointer operand | QAC | 2840 |
| Rule-18.2 | Subtraction between pointers shall only be applied to pointers that address elements of the same array | DATAFLOW | 2668, 2761, 2762, 2763, 2766, 2767, 2768 |
| Rule-18.3 | The relational operators >, >=, < and <= shall not be applied to expressions of pointer type except where they point into the same object | DATAFLOW | 2669, 2771, 2772, 2773 |
| Rule-18.6 | The address of an object with automatic or thread-local storage shall not be copied to another object that persists after the first object has ceased  | DATAFLOW | 2916, 2917, 2918 |
| Rule-18.6 | The address of an object with automatic or thread-local storage shall not be copied to another object that persists after the first object has ceased  | QAC | 3217, 3225, 3230, 4140 |
| Rule-18.9 | An object with temporary lifetime shall not undergo array-to-pointer conversion | QAC | 0450, 0455, 0459, 0464, 0465 |
| Rule-20.2 | The ', " or \ characters and the /* or // character sequences shall not occur in a header file name | QAC | 0813, 0814, 0831 |
| Rule-20.3 | The #include directive shall be followed by either a <filename> or "filename" sequence | QAC | 0817, 0821, 0840 |
| Rule-20.4 | A macro shall not be defined with the same name as a keyword | QAC | 3439 |
| Rule-20.6 | Tokens that look like a preprocessing directive shall not occur within a macro argument | QAC | 0853 |
| Rule-20.7 | Expressions resulting from the expansion of macro parameters shall be enclosed in parentheses | QAC | 3430, 3432 |
| Rule-20.8 | The controlling expression of a #if or #elif preprocessing directive shall evaluate to 0 or 1 | QAC | 0894 |
| Rule-20.9 | All identifiers used in the controlling expression of #if or #elif preprocessing directives shall be #define'd before evaluation | QAC | 3332 |
| Rule-20.11 | A macro parameter immediately following a # operator shall not immediately be followed by a ## operator | QAC | 0892 |
| Rule-20.12 | A macro parameter used as an operand to the # or ## operators, which is itself subject to further macro replacement, shall only be used as an operand  | QAC | 0893, 0895 |
| Rule-20.13 | A line whose first token is # shall be a valid preprocessing directive | QAC | 3115 |
| Rule-20.14 | All #else, #elif and #endif preprocessor directives shall reside in the same file as the #if, #ifdef or #ifndef directive to which they are related | QAC | 3317, 3318 |
| Rule-21.1 | #define and #undef shall not be used on a reserved identifier or reserved macro name | QAC | 0603, 0836, 0837, 0848, 0854, 4600, 4601, 4620, 4621 |
| Rule-21.2 | A reserved identifier or reserved macro name shall not be declared | QAC | 0602, 4602, 4603, 4604, 4605, 4606, 4607, 4608 |
| Rule-21.3 | The memory allocation and deallocation functions of <stdlib.h> shall not be used | M3CM | 5118 |
| Rule-21.4 | The standard header file <setjmp.h> shall not be used | M3CM | 5132, 5137 |
| Rule-21.5 | The standard header file <signal.h> shall not be used | M3CM | 5123, 5138 |
| Rule-21.6 | The Standard Library input/output functions shall not be used | M3CM | 5124, 5129 |
| Rule-21.7 | The Standard Library functions atof, atoi, atol and atoll of <stdlib.h> shall not be used | M3CM | 5125 |
| Rule-21.8 | The Standard Library functions abort, exit, getenv and system of <stdlib.h> shall not be used | M3CM | 5128, 5150, 5151, 5152 |
| Rule-21.9 | The Standard Library functions bsearch and qsort of <stdlib.h> shall not be used | M3CM | 5135 |
| Rule-21.10 | The Standard Library time and date functions shall not be used | M3CM | 5127, 5139 |
| Rule-21.14 | The Standard Library function memcmp shall not be used to compare null terminated strings | DATAFLOW | 2785, 2786 |
| Rule-21.15 | The pointer arguments to the Standard Library functions memcpy, memmove and memcmp shall be pointers to qualified or unqualified versions of compatibl | QAC | 1487, 1495, 1496 |
| Rule-21.16 | The pointer arguments to the Standard Library function memcmp shall point to either a pointer type, an essentially signed type, an essentially unsigne | QAC | 1488, 1489, 1490, 1491, 1497 |
| Rule-21.21 | The Standard Library system of <stdlib.h> shall not be used | M3CM | 5150 |
| Rule-21.24 | The random number generator functions of <stdlib.h> shall not be used. | M3CM | 5143 |
| Rule-21.25 | All memory synchronization operations shall be executed in sequentially consistent order. | QAC | 1193 |
| Rule-22.1 | All resources obtained dynamically by means of Standard Library functions shall be explicitly released | DATAFLOW | 2701, 2702, 2703, 2706, 2707, 2708, 2736, 2737, 2738 |
| Rule-22.3 | The same file shall not be open for read and write access at the same time on different streams | DATAFLOW | 2691, 2692, 2693 |
| Rule-22.7 | The macro EOF shall on ly be compared with the unmodified return value from any Standard Library function capable of returning EOF | QAC | 2671, 2676, 2678 |
| Rule-22.8 | The value of errno shall be set to zero prior to a call to an errno-setting-function | QAC | 2500 |
| Rule-22.9 | The value of errno shall be tested against zero after calling an errno-setting-function | QAC | 2501 |
| Rule-22.10 | The value of errno shall only be tested when the last function to be called was an errno-setting-function | QAC | 2503 |
| Rule-22.11 | A thread that was previously either joined or detached shall not be subsequently joined nor detached | MTA | 1776 |
| Rule-22.13 | Thread objects, thread synchronization objects and thread-specific storage pointers shall have appropriate storage duration | QAC | 2034 |
| Rule-22.15 | Thread synchronization objects and thread-specific storage pointers shall not be destroyed until after all threads accessing them have terminated | MTA | 1789, 1790 |
| Rule-22.16 | All mutex objects locked by a thread shall be explicitly unlocked by the same thread | DATAFLOW | 4946, 4947 |
| Rule-22.17 | No thread shall unlock a mutex or call cnd_wait() or cnd_timedwait() for a mutex it has not locked before | DATAFLOW | 4981, 4982 |
| Rule-22.18 | Non-recursive mutexes shall not be recursively locked | DATAFLOW | 4986, 4987 |
| Rule-22.19 | A condition variable shall be associated with at most one mutex object | MTA | 1769 |
| Dir-1.1 | Any implementation-defined behaviour on which the output of the program depends shall be documented and understood Assisted by DATAFLOW: 2851, 2852, 2 | — | — |
| Dir-4.1 | Run-time failures shall be minimized Assisted by DATAFLOW: 2791, 2792, 2793, 2794, 2801, 2802, 2803, 2804, 2811, 2812, 2813, 2821, 2822, 2823, 2831, 2 | — | — |
| Dir-4.3 | Assembly language shall be encapsulated and isolated Assisted by QAC: 3006, 3008 | — | — |
| Dir-4.7 | If a function returns error information, then that error information shall be tested Assisted by QAC: 2504 | — | — |
| Dir-4.10 | Precautions shall be taken in order to prevent the contents of a header file being included more then once Assisted by QAC: 0883 | — | — |
| Dir-4.12 | Dynamic memory allocation shall not be used Assisted by M3CM: 5118 Page 37 | — | — |
| Dir-4.14 | The validity of values received from external sources shall be checked Assisted by DATAFLOW: 2956 | — | — |
| Dir-5.1 | There shall be no data races between threads Assisted by MTA: 1765, 1766, 1770, 1774, 1775 | — | — |
| Dir-5.2 | There shall be no deadlocks between threads Assisted by MTA: 1767, 1768 | — | — |
| Dir-2.1 | All source files shall compile without any compilation errors | — | — |
| Dir-3.1 | All code shall be traceable to documented requirements | — | — |
| Dir-4.11 | The validity of values passed to library functions shall be checked | — | — |
| Dir-4.15 | Evaluation of floating-point expressions shall not lead to the undetected generation of infinities and NaNs | — | — |
| Dir-5.3 | There shall be no dynamic thread creation | — | — |
| Rule-1.1-C11 | The program shall contain no violations of the standard C syntax and constraints, and shall not exceed the implementation's translation limits | QAC | 2050, 2051, 3335 |
| Rule-1.4-C11 | Emergent language features shall not be used | QAC | 1081, 1084 |
| Rule-8.15-C11 | All declarations of an object with an explicit alignment specification shall specify the same alignment. | QAC | 1166, 1167 |
| Rule-11.3-C11 | A conversion shall not be performed between a pointer to object type and a pointer to a different object type. | QAC | 2041 |
| Rule-11.8-C11 | A conversion shall not remove any const, volatile or _Atomic qualification from the type pointed to by a pointer. | QAC | 2039, 2040 |
| Rule-11.10-C11 | The _Atomic qualifier shall not be applied to the incomplete type void. | QAC | 2038 |
| Rule-12.6-C11 | Structure and union members of atomic objects shall not be directly accessed. | QAC | 2037 |
| Rule-17.10-C11 | A function declared with a _Noreturn function specifier shall have void return type | QAC | 1085 |
| Rule-20.4-C11 | A macro shall not be defined with the same name as a keyword | QAC | 3468 |
| Rule-21.26-C11 | The Standard Library function mtx_timedlock() shall only be invoked on mutex objects of appropriate mutex type | DATAFLOW | 3537 |
| Rule-23.2-C11 | A generic selection that is not expanded from a macro shall not contain potential side effects in the controlling expression | QAC | 1172 |
| Rule-23.4-C11 | A generic association shall list an appropriate type | QAC | 1128 |
| Rule-23.6-C11 | The controlling expression of a generic selection shall have an essential type that matches its standard type | QAC | 1175 |
| Rule-23.8-C11 | A default association shall appear as either the first or the last association of a generic selection | QAC | 1178 |
| Dir-1.1-C11 | Any implementation-defined behaviour on which the output of the program depends shall be documented and understood Assisted by QAC: 0371, 0372, 0375,  | — | — |
| Rule-1.1-C90 | The program shall contain no violations of the standard C syntax and constraints, and shall not exceed the implementation's translation limits | QAC | 3421 |
| Rule-8.1-C90 | Types shall be explicitly specified | QAC | 2050, 2051 |
| Rule-21.1-C90 | #define and #undef shall not be used on a reserved identifier or reserved macro name | QAC | 3468 |
| Dir-1.1-C90 | Any implementation-defined behaviour on which the output of the program depends shall be documented and understood Assisted by M3CM: 5131, 5136, 5141  | — | — |
| Rule-1.1-C99 | The program shall contain no violations of the standard C syntax and constraints, and shall not exceed the implementation's translation limits | QAC | 2050, 2051, 3335 |
| Rule-20.4-C99 | A macro shall not be defined with the same name as a keyword | QAC | 3468 |
| Dir-1.1-C99 | Any implementation-defined behaviour on which the output of the program depends shall be documented and understood Assisted by QAC: 0371, 0372, 0375,  | — | — |
| Rule-1.5 | Obsolescent language features shall not be used | DATAFLOW | 4871, 4872, 4873 |
| Rule-1.5 | Obsolescent language features shall not be used | M3CM | 5142 |
| Rule-1.5 | Obsolescent language features shall not be used | QAC | 1169, 3001, 3002, 3224, 3228 |
| Rule-3.2 | Line-splicing shall not be used in // comments. | QAC | 0247 |
| Rule-7.6 | The small integer variants of the minimum-width integer constant macros shall not be used | QAC | 3187 |
| Rule-8.10 | An inline function shall be declared with the static storage class | QAC | 3240, 3241, 3242, 3243 |
| Rule-8.14 | The restrict type qualifier shall not be used | QAC | 1057 |
| Rule-9.4 | An element of an object shall not be initialized more than once | QAC | 1397, 1398, 1399 |
| Rule-9.5 | Where designated initializers are used to initialize an array object the size of the array shall be specified explicitly | QAC | 3676 |
| Rule-13.1 | Initializer lists shall not contain persistent side-effects | QAC | 3421 |
| Rule-18.7 | Flexible array members shall not be declared | QAC | 1060 |
| Rule-18.8 | Variable-length arrays shall not be used | QAC | 1051 |
| Rule-21.12 | The standard header file <fenv.h> shall not be used | M3CM | 5136 |
| Rule-21.23 | All operand arguments to any multi-argument type-generic macros declared in <tgmath.h> shall have the same standard type | QAC | 1163 |
| Rule-1.2 | Language extensions should not be used | QAC | 0246, 0497, 0551, 0601, 0633, 0635, 0660, 0662, 0710, 0830 (+70 more) |
| Rule-2.3 | A project should not contain unused type declarations | QAC | 3205 |
| Rule-2.3 | A project should not contain unused type declarations | RCMA | 1535 |
| Rule-2.4 | A project should not contain unused tag declarations | QAC | 3213 |
| Rule-2.4 | A project should not contain unused tag declarations | RCMA | 1536, 1755 |
| Rule-2.5 | A project should not contain unused macro definitions | RCMA | 1534 |
| Rule-2.6 | A function should not contain unused label declarations | QAC | 3202 |
| Rule-2.7 | A function should not contain unused parameters | QAC | 3206 |
| Rule-2.8 | A project should not contain unused object definitions | QAC | 3205, 3207 |
| Rule-2.8 | A project should not contain unused object definitions | RCMA | 1502 |
| Rule-4.2 | Trigraphs should not be used | QAC | 3601 |
| Rule-5.9 | Identifiers that define objects or functions with internal linkage should be unique | RCMA | 1525, 1527, 1528, 1759 |
| Rule-8.7 | Functions and objects should not be defined with external linkage if they are referenced in only one translation unit | RCMA | 1504, 1505, 1514 |
| Rule-8.9 | An object should be declared at block scope if its identifier only appears in a single function | QAC | 3218 |
| Rule-8.9 | An object should be declared at block scope if its identifier only appears in a single function | RCMA | 1514, 1533 |
| Rule-8.11 | When an array with external linkage is declared, its size should be explicitly specified | QAC | 3684 |
| Rule-8.13 | A pointer should point to a const-qualified type whenever possible | QAC | 3673, 3677, 3678, 3679, 3694 |
| Rule-10.5 | The value of an expression should not be cast to an inappropriate essential type | QAC | 4301, 4302, 4303, 4304, 4305, 4310, 4312, 4315, 4320, 4322 (+7 more) |
| Rule-11.4 | A conversion should not be performed between a pointer to object and an integer type | QAC | 0303, 0306, 0360, 0361, 0362 |
| Rule-11.5 | A conversion should not be performed from pointer to void into pointer to object | QAC | 0316, 0317 |
| Rule-12.1 | The precedence of operators within expressions should be made explicit | QAC | 3389, 3391, 3392, 3394, 3395, 3396, 3397, 3433 |
| Rule-12.3 | The comma operator should not be used | QAC | 3417, 3418 |
| Rule-12.4 | Evaluation of constant expressions should not lead to unsigned integer wrap-around | QAC | 2910 |
| Rule-13.3 | A full expression containing an increment (++) or decrement (--) operator should have no other potential side effects other than that caused by the in | QAC | 3387, 3440 |
| Rule-13.4 | The result of an assignment operator should not be used | QAC | 3226, 3326 |
| Rule-15.1 | The goto statement should not be used | QAC | 2001 |
| Rule-15.4 | There should be no more than one break or goto statement used to terminate any iteration statement | QAC | 0771, 0772 |
| Rule-15.5 | A function should have a single point of exit at the end | DATAFLOW | 2889 |
| Rule-17.8 | A function parameter should not be modified | QAC | 1338, 1339, 1340 |
| Rule-17.12 | A function identifier should only be used with either a preceding &, or with a parenthesised parameter list | QAC | 3635 |
| Rule-18.4 | The +, -, += and -= operators should not be applied to an expression of pointer type | QAC | 0488, 0489 |
| Rule-18.5 | Declarations should contain no more than two levels of pointer nesting | QAC | 3260, 3261, 3262, 3263 |
| Rule-19.2 | The union keyword should not be used | QAC | 0750, 0759 |
| Rule-20.1 | #include directives should only be preceded by preprocessor directives or comments | M3CM | 5087 |
| Rule-20.5 | #undef should not be used | QAC | 0841, 0847 |
| Rule-20.10 | The # and ## preprocessor operators should not be used | QAC | 0341, 0342 |
| Dir-4.2 | All usage of assembly language should be documented Assisted by QAC: 1003, 1006 | — | — |
| Dir-4.4 | Sections of code should not be "commented out" Assisted by QAC: 2052, 2053 | — | — |
| Dir-4.5 | Identifiers in the same name space with overlapping visibility should be typographically unambiguous Assisted by RCMA: 1710 | — | — |
| Dir-4.6 | typedefs that indicate size and signedness should be used in place of the basic numerical types Assisted by M3CM: 5209 | — | — |
| Dir-4.8 | If a pointer to a structure or union is never dereferenced within a translation unit, then the implementation of the object should be hidden Assisted  | — | — |
| Dir-4.9 | A function should be used in preference to a function-like macro where they are interchangeable Assisted by QAC: 3469, 3471, 3472, 3473 | — | — |
| Dir-4.13 | Functions which are designed to provide operations on a resource should be called in an appropriate sequence Assisted by DATAFLOW: 2726, 2727, 2728, 2 | — | — |
| Rule-8.16-C11 | The alignment specification of zero should not appear in an object declaration. | QAC | 1165 |
| Rule-8.17-C11 | At most one explicit alignment specifier should appear in an object declaration. | QAC | 1164 |
| Rule-17.11-C11 | A function that never returns should be declared with a _Noreturn function specifier | DATAFLOW | 2885 |
| Rule-23.1-C11 | A generic selection should only be expanded from a macro | QAC | 1177 |
| Rule-23.3-C11 | A generic selection should contain at least one non-default association | QAC | 1171 |
| Rule-23.5-C11 | A generic selection should not depend on implicit pointer type conversion | QAC | 1174 |
| Rule-23.7-C11 | A generic selection that is expanded from a macro should evaluate its argument only once | QAC | 1176 |
| Rule-1.2-C90 | Language extensions should not be used | M3CM | 5131, 5136, 5141 |
| Rule-1.2-C90 | Language extensions should not be used | QAC | 0180, 0181, 0320, 0604, 0617, 0618, 0850, 0930, 1011, 1018 (+29 more) |
| Rule-1.2-C99 | Language extensions should not be used | QAC | 1077, 1078, 1079, 1081, 1082, 1084 |
| Rule-21.11 | The standard header file <tgmath.h> should not be used | M3CM | 5131, 5141 |
