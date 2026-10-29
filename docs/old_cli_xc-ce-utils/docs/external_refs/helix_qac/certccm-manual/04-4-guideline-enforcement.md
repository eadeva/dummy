# 4 | Guideline Enforcement

4 | Guideline Enforcement
This report lists all the CERT C sections (Preprocessor (PRE), Declarations and Initialization (DCL), Expression
(EXP), and so on), and, within each section, lists the rules under a Rule sub-section, and the recommendations under a
Recommendation subsection. Within each sub-section, the guidelines are grouped in accordance with whether they are
Enforced or Unenforced.
Note:
Where a guideline cannot be enforced by static analysis, it is classified as Not Statically Enforceable,
and is not taken into account in the Enforced/Unenforced Rules Percentages at the end of the section.
If automatic help can be provided to enforce such a guideline, then it is further classified as Assisted.
Otherwise, it is referred to as Unassisted.
CSV Rule Summary
A CSV file is provided with the RCF that links the rules to the messages that enforce them. This file can be used to import
enforcement information into spreadsheets for further processing.
There are two record formats: Messages and Summary. The Messages entries links each rule to each message, along
with its text and ID. The Summary entries links a single rule to all mapped messages specified in a comma separated
string.
When loading the CSV in Excel, the recommended steps are:
1. Open the Data menu and select From Text/CSV.
2. Select the file to import.
3. Open the Data Type Detection menu and select Do not detect data types.
Preprocessor (PRE)
Rule
Enforced
Rule Id
Rule
PRE30
Do not create a universal character name through concatenation
Enforced by QAC:
0905
PRE31
Avoid side effects in arguments to unsafe macros
Enforced by QAC:
3462, 3463, 3464, 3465, 3466, 3467
PRE32
Do not use preprocessor directives in invocations of function-like macros
Enforced by QAC:
0853
Total: 3
Page 10


---
*Page 10*

Recommendation
Enforced
Rule Id
Rule
PRE00
Prefer inline or static functions to function-like macros
Enforced by QAC:
3453
PRE01
Use parentheses within macros around parameter names
Enforced by QAC:
3410
PRE02
Macro replacement lists should be parenthesized
Enforced by QAC:
3409
PRE03
Prefer typedefs to defines for encoding non-pointer types
Enforced by QAC:
3413
PRE04
Do not reuse a standard header file name
Enforced by CERTCCM:
5001
PRE05
Understand macro replacement when concatenating tokens or performing stringification
Enforced by QAC:
0341, 0342, 0801, 0802, 0803, 0811, 0872, 0880, 0881, 0884
PRE06
Enclose header files in an inclusion guard
Enforced by QAC:
0883
PRE07
Avoid using repeated question marks
Enforced by QAC:
3601
PRE08
Guarantee that header file names are unique
Enforced by CERTCCM:
5002
Page 11


---
*Page 11*

Rule Id
Rule
PRE09
Do not replace secure functions with deprecated or obsolescent functions
Enforced by CERTCCM:
5003
PRE10
Wrap multi-statement macros in a do-while loop
Enforced by QAC:
3412, 3458
PRE11
Do not conclude macro definitions with a semicolon
Enforced by QAC:
3412
PRE12
Do not define unsafe macros
Enforced by QAC:
3456
Total: 13
Declarations and Initialization (DCL)
Rule
Enforced
Rule Id
Rule
DCL30
Declare objects with appropriate storage durations
Enforced by QAC:
3217, 3225, 3230, 4140
DCL31
Declare identifiers before using them
Enforced by QAC:
0434, 2050, 2051, 3335
DCL36
Do not declare an identifier with conflicting linkage classifications
Enforced by QAC:
0625
Page 12


---
*Page 12*

Rule Id
Rule
DCL37
Do not declare or define a reserved identifier
Enforced by QAC:
0602, 0603, 4600, 4601, 4602, 4603, 4604, 4605, 4606, 4607, 4608, 4620, 4621, 4622, 4623, 4624,
4640, 4641, 4642, 4643, 4644, 4645
DCL38
Use the correct syntax when declaring a flexible array member
Enforced by QAC:
1037, 1039
DCL39
Avoid information leakage when passing a structure across a trust boundary
Enforced by DATAFLOW:
4941, 4942, 4943
DCL40
Do not create incompatible declarations of the same function or object
Enforced by QAC:
0776, 0778, 0779, 0789
Enforced by RCMA:
1510
DCL41
Do not declare variables inside a switch statement before the first case label
Enforced by QAC:
2008, 2882, 3234
Total: 8
Recommendation
Enforced
Rule Id
Rule
DCL00
Const-qualify immutable objects
Enforced by QAC:
3204, 3227, 3232, 3673, 3677, 3694
DCL01
Do not reuse variable names in subscopes
Enforced by QAC:
0795, 0796, 2547, 3334
Page 13


---
*Page 13*

Rule Id
Rule
DCL05
Use typedefs of non-pointer types only
Enforced by CERTCCM:
5004
DCL06
Use meaningful symbolic constants to represent literal values
Enforced by QAC:
3120, 3121, 3122, 3123, 3131, 3132
DCL07
Include the appropriate type information in function declarators
Enforced by QAC:
1304, 2050, 3331, 3335, 3408, 3450
DCL10
Maintain the contract between the writer and caller of variadic functions
Enforced by QAC:
0184, 0185
DCL11
Understand the type issues associated with variadic functions
Enforced by QAC:
0179, 0184, 0185, 0186, 0190, 0191, 0192, 0193, 0194, 0195, 0196, 0197, 0198, 0199, 0200, 0201,
0206, 0207, 0208
DCL13
Declare function parameters that are pointers to values not changed by the function as const
Enforced by QAC:
0431, 3673, 3677, 3694
DCL15
Declare file-scope objects or functions that do not need external linkage as static
Enforced by RCMA:
1504, 1531
DCL16
Use 'L', not 'l', to indicate a long value
Enforced by QAC:
1280
DCL18
Do not begin integer constants with 0 when specifying a decimal value
Enforced by QAC:
0339, 1272
Page 14


---
*Page 14*

Rule Id
Rule
DCL19
Minimize the scope of variables and functions
Enforced by QAC:
3210, 3218
Enforced by RCMA:
1504, 1505, 1531, 1532
DCL20
Explicitly specify void when a function accepts no arguments
Enforced by QAC:
3001, 3007
DCL21
Understand the storage of compound literals
Enforced by QAC:
1054, 3217
DCL23
Guarantee that mutually visible identifiers are unique
Enforced by QAC:
0627, 0776, 0777, 0778, 0779, 0789, 0791, 0793
Total: 15
Expressions (EXP)
Rule
Enforced
Rule Id
Rule
EXP30
Do not depend on the order of evaluation for side effects
Enforced by QAC:
0400, 0401, 0402, 0403, 0404, 0405
EXP32
Do not access a volatile object through a nonvolatile reference
Enforced by QAC:
0312, 0562, 0563, 0673, 0674
EXP33
Do not read uninitialized memory
Enforced by DATAFLOW:
2726, 2727, 2728, 2961, 2962, 2963, 2966, 2967, 2968, 2971, 2972, 2973, 2976, 2977, 2978
Page 15


---
*Page 15*

Rule Id
Rule
EXP34
Do not dereference null pointers
Enforced by DATAFLOW:
2810, 2811, 2812, 2813
EXP35
Do not modify objects with temporary lifetime
Enforced by QAC:
0450, 0455, 0459, 0464, 0465
EXP36
Do not cast pointers into more strictly aligned pointer types
Enforced by QAC:
0326, 3305
EXP37
Call functions with the correct number and type of arguments
Enforced by QAC:
1331, 1332, 1333, 3002, 3320, 3335
EXP39
Do not access a variable through a pointer of an incompatible type
Enforced by QAC:
0310, 0751, 3305
EXP40
Do not modify constant objects
Enforced by QAC:
0563
EXP42
Do not compare padding data
Enforced by DATAFLOW:
4726, 4727, 4728, 4729
EXP43
Avoid undefined behavior when using restrict-qualified pointers
Enforced by QAC:
1057
EXP44
Do not rely on side effects in operands to sizeof, _Alignof, or _Generic
Enforced by QAC:
3307
Page 16


---
*Page 16*

Rule Id
Rule
EXP45
Do not perform assignments in selection statements
Enforced by QAC:
3314, 3326, 3344, 3416
EXP46
Do not use a bitwise operator with a Boolean-like operand
Enforced by QAC:
3344, 4502
EXP47
Do not call va_arg with an argument of the incorrect type
Enforced by DATAFLOW:
4901, 4902, 4903, 4904
Total: 15
Recommendation
Enforced
Rule Id
Rule
EXP00
Use parentheses for precedence of operation
Enforced by QAC:
3389, 3390, 3391, 3392, 3393, 3394, 3395, 3396, 3397, 3398, 3399, 3400
EXP02
Be aware of the short-circuit behavior of the logical AND and OR operators
Enforced by QAC:
3415
EXP03
Do not assume the size of a structure is the sum of the sizes of its members
Enforced by QAC:
0697
EXP05
Do not cast away a const qualification
Enforced by QAC:
0311, 0431
EXP07
Do not diminish the benefits of constants by assuming their values in expressions
Enforced by QAC:
3120, 3121, 3122, 3123, 3131, 3132
Page 17


---
*Page 17*

Rule Id
Rule
EXP08
Ensure pointer arithmetic is used correctly
Enforced by DATAFLOW:
2930, 2931, 2932, 2933
Enforced by QAC:
0488
EXP10
Do not depend on the order of evaluation of subexpressions or the order in which side effects take place
Enforced by QAC:
0400, 0401, 0402, 0403, 0404, 0405, 3226, 3326
EXP11
Do not make assumptions regarding the layout of structures with bit-fields
Enforced by QAC:
0310, 0751
EXP12
Do not ignore values returned by functions
Enforced by QAC:
3200
EXP13
Treat relational and equality operators as if they were nonassociative
Enforced by QAC:
3392, 3401, 4111, 4112, 4113
EXP15
Do not place a semicolon on the same line as an if, for, or while statement
Enforced by QAC:
3109
EXP16
Do not compare function pointers to constant values
Enforced by QAC:
0428, 3004, 3344
EXP19
Use braces for the body of an if, for, or while statement
Enforced by QAC:
2212
EXP20
Perform explicit tests to determine success, true and false, and equality
Enforced by QAC:
3344, 4116
Total: 14
Page 18


---
*Page 18*

Integers (INT)
Rule
Enforced
Rule Id
Rule
INT30
Ensure that unsigned integer operations do not wrap
Enforced by DATAFLOW:
2911, 2912, 2913
Enforced by QAC:
2910, 3383, 3384, 3385, 3386
INT31
Ensure that integer conversions do not result in lost or misinterpreted data
Enforced by DATAFLOW:
2851, 2852, 2853, 2856, 2857, 2858, 2891, 2892, 2893, 2896, 2897, 2898, 2901, 2902, 2903, 2906,
2907, 2908
Enforced by QAC:
2850, 2855, 2890, 2895, 2900, 2905
INT32
Ensure that operations on signed integers do not result in overflow
Enforced by DATAFLOW:
2801, 2802, 2803, 2861, 2862, 2863
Enforced by QAC:
2800, 2860
INT33
Ensure that division and remainder operations do not result in divide-by-zero errors
Enforced by DATAFLOW:
2831, 2832, 2833
Enforced by QAC:
2830
INT34
Do not shift an expression by a negative number of bits or by greater than or equal to the number of bits
that exist in the operand
Enforced by DATAFLOW:
2791, 2792, 2793
Enforced by QAC:
0499, 2790
Page 19


---
*Page 19*

Rule Id
Rule
INT35
Use correct integer precisions
Enforced by QAC:
0582
INT36
Converting a pointer to integer or integer to pointer
Enforced by QAC:
0303, 0305, 0306, 0309, 0324, 0326, 0360, 0361, 0362
Total: 7
Recommendation
Enforced
Rule Id
Rule
INT02
Understand integer conversion rules
Enforced by QAC:
1257, 1820, 1821, 1822, 1823, 1824, 1830, 1831, 1832, 1833, 1834, 1860, 1861, 1862, 1863, 1864,
1880, 1881, 1882, 2120, 2130, 4397, 4434, 4446
INT04
Enforce limits on integer values originating from tainted sources
Enforced by DATAFLOW:
2794, 2804, 2854, 2859, 2864, 2894, 2899, 2904, 2909, 2914, 2924, 2944, 2949, 2954, 2956, 2959
INT05
Do not use input functions to convert character data if they cannot handle all possible inputs
Enforced by CERTCCM:
5005
INT07
Use only explicitly signed or unsigned char type for numeric values
Enforced by QAC:
1292, 1293, 4401, 4421, 4431, 4441, 4451
INT08
Verify that all integer values are in range
Enforced by DATAFLOW:
2801, 2802, 2803, 2911, 2912, 2913
Enforced by QAC:
2800, 2910
Page 20


---
*Page 20*

Rule Id
Rule
INT09
Ensure enumeration constants map to unique values
Enforced by QAC:
0724
INT10
Do not assume a positive remainder when using the % operator
Enforced by QAC:
3103
INT12
Do not make assumptions about the type of a plain int bit-field when used in an expression
Enforced by QAC:
0634, 0635
INT13
Use bitwise operators only on unsigned operands
Enforced by QAC:
4532, 4533, 4534, 4543, 4544
INT16
Do not make assumptions about representation of signed integers
Enforced by DATAFLOW:
2941, 2942, 2943, 2946, 2947, 2948
Enforced by QAC:
2940, 2945
INT18
Evaluate integer expressions in a larger size before comparing or assigning to that size
Enforced by QAC:
1890, 1891, 1892, 1893, 1894, 1895, 4490, 4491, 4492
Total: 11
Floating Point (FLP)
Rule
Enforced
Rule Id
Rule
FLP30
Do not use floating-point variables as loop counters
Enforced by QAC:
3339, 3340, 3342
Page 21


---
*Page 21*

Rule Id
Rule
FLP32
Prevent or detect domain and range errors in math functions
Enforced by CERTCCM:
5025
FLP34
Ensure that floating-point conversions are within range of the new type
Enforced by QAC:
4450, 4451, 4452, 4453, 4454, 4462, 4465
FLP36
Preserve precision when converting integral values to floating-point type
Enforced by QAC:
1260, 1263, 1298, 1299, 1800, 1802, 1803, 1804, 4117, 4435, 4437, 4445
FLP37
Do not use object representations to compare floating-point values
Enforced by QAC:
1490
Total: 5
Recommendation
Enforced
Rule Id
Rule
FLP00
Understand the limitations of floating-point numbers
Enforced by QAC:
0275, 0581, 1490, 3339, 3340, 3341, 3342, 3362
FLP02
Avoid using floating-point numbers when precise computation is needed
Enforced by QAC:
0790
FLP06
Convert integers to floating point for floating point operations
Enforced by QAC:
4117, 4118
Total: 3
Arrays (ARR)
Rule
Enforced
Page 22


---
*Page 22*

Rule Id
Rule
ARR30
Do not form or use out-of-bounds pointers or array subscripts
Enforced by DATAFLOW:
2820, 2821, 2822, 2823, 2840, 2841, 2842, 2843, 2930, 2931, 2932, 2933, 2935, 2936, 2937, 2938,
2950, 2951, 2952, 2953
Enforced by QAC:
2840
ARR32
Ensure size arguments for variable length arrays are in a valid range
Enforced by QAC:
1051
ARR36
Do not subtract or compare two pointers that do not refer to the same array
Enforced by DATAFLOW:
2668, 2669, 2761, 2762, 2763, 2766, 2767, 2768, 2771, 2772, 2773
Enforced by QAC:
0487, 0513
ARR37
Do not add or subtract an integer to a pointer to a non-array object
Enforced by DATAFLOW:
2930, 2931, 2932, 2933
ARR38
Guarantee that library functions do not form invalid pointers
Enforced by DATAFLOW:
2840, 2841, 2842, 2843, 2845, 2846, 2847, 2848, 2935, 2936, 2937, 2938, 4880, 4881, 4882, 4883
Enforced by QAC:
2840
ARR39
Do not add or subtract a scaled integer to a pointer
Enforced by DATAFLOW:
4955, 4956, 4957
Total: 6
Recommendation
Enforced
Page 23


---
*Page 23*

Rule Id
Rule
ARR02
Explicitly specify array bounds, even if implicitly defined by an initializer
Enforced by QAC:
0678, 0688, 3674, 3684
Total: 1
Characters and Strings (STR)
Rule
Enforced
Rule Id
Rule
STR30
Do not attempt to modify string literals
Enforced by QAC:
0556, 0752, 0753, 0754
STR31
Guarantee that storage for strings has sufficient space for character data and the null terminator
Enforced by CERTCCM:
5009, 5038
Enforced by DATAFLOW:
2840, 2841, 2842, 2843, 2845, 2846, 2847, 2848, 2930, 2931, 2932, 2933, 2935, 2936, 2937, 2938
Enforced by QAC:
2840
STR32
Do not pass a non-null-terminated character sequence to a library function that expects a string
Enforced by DATAFLOW:
2835, 2836, 2839
STR34
Cast characters to unsigned char before converting to larger integer sizes
Enforced by QAC:
2140, 2141, 2143, 2144, 2145, 2147, 2148, 2149, 2151, 2152, 2153, 2155
STR37
Arguments to character-handling functions must be representable as an unsigned char
Enforced by DATAFLOW:
2796, 2797, 2798, 2799
Enforced by QAC:
4413, 4414
Page 24


---
*Page 24*

Rule Id
Rule
STR38
Do not confuse narrow and wide character strings and functions
Enforced by QAC:
0432
Total: 6
Recommendation
Enforced
Rule Id
Rule
STR04
Use plain char for characters in the basic character set
Enforced by QAC:
0432, 0674, 0699
STR05
Use pointers to const when referring to string literals
Enforced by QAC:
0752, 0753
STR06
Do not assume that strtok() leaves the parse string unchanged
Enforced by CERTCCM:
5007
STR07
Use the bounds-checking interfaces for string manipulation
Enforced by CERTCCM:
5008
STR09
Don't assume numeric values for expressions with type plain character
Enforced by QAC:
2106, 2107
STR10
Do not concatenate different type of string literals
Enforced by QAC:
0874
STR11
Do not specify the bound of a character array initialized with a string literal
Enforced by QAC:
1312
Total: 7
Page 25


---
*Page 25*

Memory Management (MEM)
Rule
Enforced
Rule Id
Rule
MEM30
Do not access freed memory
Enforced by DATAFLOW:
4866, 4867, 4868, 4871, 4872, 4873
MEM31
Free dynamically allocated memory when no longer needed
Enforced by DATAFLOW:
2706, 2707, 2708
MEM33
Allocate and copy structures containing a flexible array member dynamically
Enforced by QAC:
1061, 1062, 1063, 1064
MEM34
Only free memory allocated dynamically
Enforced by DATAFLOW:
2721, 2722, 2723
MEM35
Allocate sufficient memory for an object
Enforced by DATAFLOW:
2840, 2841, 2842, 2843, 2935, 2936, 2937, 2938
Enforced by QAC:
0696, 0701, 1069, 1071, 1073, 2840
MEM36
Do not modify the alignment of objects by calling realloc()
Enforced by CERTCCM:
5027
Total: 6
Recommendation
Enforced
Rule Id
Rule
MEM02
Immediately cast the result of a memory allocation function call into a pointer to the allocated type
Enforced by QAC:
0695
Page 26


---
*Page 26*

Rule Id
Rule
MEM03
Clear sensitive information stored in reusable resources
Enforced by CERTCCM:
5010
MEM05
Avoid large stack allocations
Enforced by QAC:
1051, 3670
Enforced by RCMA:
1520
Total: 3
Input Output (FIO)
Rule
Enforced
Rule Id
Rule
FIO30
Exclude user input from format strings
Enforced by DATAFLOW:
4916, 4917, 4918
FIO32
Do not perform operations on devices that are only appropriate for files
Enforced by DATAFLOW:
4921, 4922, 4923
FIO34
Distinguish between characters read from a file and EOF or WEOF
Enforced by QAC:
2676, 2678
FIO37
Do not assume that fgets() or fgetws() returns a nonempty string when successful
Enforced by DATAFLOW:
4911, 4912, 4913
FIO38
Do not copy a FILE object
Enforced by QAC:
1485
Page 27


---
*Page 27*

Rule Id
Rule
FIO39
Do not alternately input and output from a stream without an intervening flush or positioning call
Enforced by DATAFLOW:
4711, 4712, 4713
FIO40
Reset strings on fgets() or fgetws() failure
Enforced by DATAFLOW:
4861, 4862, 4863
FIO41
Do not call getc(), putc(), getwc(), or putwc() with a stream argument that has side effects
Enforced by CERTCCM:
5036
FIO42
Close files when they are no longer needed
Enforced by DATAFLOW:
2701, 2702, 2703
FIO44
Only use values for fsetpos() that are returned from fgetpos()
Enforced by DATAFLOW:
4841, 4842, 4843
FIO45
Avoid TOCTOU race conditions while accessing files
Enforced by DATAFLOW:
4851, 4852, 4853
FIO46
Do not access a closed file
Enforced by DATAFLOW:
2696, 2697, 2698
FIO47
Use valid format strings
Enforced by QAC:
0161, 0162, 0163, 0164, 0165, 0166, 0167, 0168, 0169, 0170, 0171, 0172, 0173, 0174, 0175, 0176,
0177, 0178, 0179, 0180, 0184, 0185, 0190, 0191, 0192, 0193, 0194, 0195, 0196, 0197, 0198, 0199,
0200, 0201, 0202, 0204, 0206, 0209
Total: 13
Recommendation
Enforced
Page 28


---
*Page 28*

Rule Id
Rule
FIO01
Be careful using functions that use file names for identification
Enforced by CERTCCM:
5011
FIO03
Do not make assumptions about fopen() and file creation
Enforced by CERTCCM:
5012
FIO06
Create files with appropriate access permissions
Enforced by CERTCCM:
5013
FIO08
Take care when calling remove() on an open file
Enforced by CERTCCM:
5014
FIO10
Take care when using the rename() function
Enforced by CERTCCM:
5015
FIO21
Do not create temporary files in shared directories
Enforced by CERTCCM:
5016
Total: 6
Environment (ENV)
Rule
Enforced
Rule Id
Rule
ENV30
Do not modify the object referenced by the return value of certain functions
Enforced by DATAFLOW:
4751, 4752, 4753
Enforced by QAC:
1492, 1493, 1494
Page 29


---
*Page 29*

Rule Id
Rule
ENV31
Do not rely on an environment pointer following an operation that may invalidate it
Enforced by DATAFLOW:
4991, 4992, 4993
ENV32
All exit handlers must return normally
Enforced by DATAFLOW:
4856, 4857, 4858
ENV33
Do not call system()
Enforced by CERTCCM:
5018
ENV34
Do not store pointers returned by certain functions
Enforced by DATAFLOW:
2681, 2682, 2683
Total: 5
Recommendation
Enforced
Rule Id
Rule
ENV03
Sanitize the environment when invoking external programs
Enforced by CERTCCM:
5017
Total: 1
Signals (SIG)
Rule
Enforced
Rule Id
Rule
SIG30
Call only asynchronous-safe functions within signal handlers
Enforced by QAC:
2028, 2030
Page 30


---
*Page 30*

Rule Id
Rule
SIG31
Do not access shared objects in signal handlers
Enforced by QAC:
2029, 2030
SIG34
Do not call signal() from within interruptible signal handlers
Enforced by CERTCCM:
5021
SIG35
Do not return from a computational exception signal handler
Enforced by DATAFLOW:
4846, 4847, 4848
Total: 4
Recommendation
Enforced
Rule Id
Rule
SIG00
Mask signals handled by noninterruptible signal handlers
Enforced by CERTCCM:
5019
SIG01
Understand implementation-specific details regarding signal handler persistence
Enforced by CERTCCM:
5020
Total: 2
Error Handling (ERR)
Rule
Enforced
Rule Id
Rule
ERR30
Set errno to zero before calling a library function known to set errno, and check errno only after the
function returns a value indicating failure
Enforced by QAC:
2500, 2501, 2502, 2503
Page 31


---
*Page 31*

Rule Id
Rule
ERR32
Do not rely on indeterminate values of errno
Enforced by DATAFLOW:
4781, 4782, 4783
Enforced by QAC:
2031
ERR33
Detect and handle standard library errors
Enforced by QAC:
3200
ERR34
Detect errors when converting a string to a number
Enforced by CERTCCM:
5030
Total: 4
Concurrency (CON)
Rule
Enforced
Rule Id
Rule
CON30
Clean up thread-specific storage
Enforced by MTA:
1780, 1781, 1782, 1783, 1784
CON31
Do not destroy a mutex while it is locked
Enforced by DATAFLOW:
4961, 4962
CON32
Prevent data races when accessing bit-fields from multiple threads
Enforced by MTA:
1774, 1775
Page 32


---
*Page 32*

Rule Id
Rule
CON33
Avoid race conditions when using library functions
Enforced by CERTCCM:
5037
Enforced by DATAFLOW:
4976, 4977
CON34
Declare objects shared between threads with appropriate storage durations
Enforced by DATAFLOW:
4926, 4927, 4928
CON35
Avoid deadlock by locking in a predefined order
Enforced by MTA:
1772, 1773
CON36
Wrap functions that can spuriously wake up in a loop
Enforced by QAC:
2027
CON37
Do not call signal() in a multithreaded program
Enforced by CERTCCM:
5021
CON38
Preserve thread safety and liveness when using condition variables
Enforced by MTA:
1778, 1779
CON39
Do not join or detach a thread that was previously joined or detached
Enforced by MTA:
1776
CON40
Do not refer to an atomic variable twice in an expression
Enforced by QAC:
1114, 1115, 1116
CON41
Wrap functions that can fail spuriously in a loop
Enforced by QAC:
2026
Page 33


---
*Page 33*

Rule Id
Rule
CON43
Do not allow data races in multithreaded code
Enforced by MTA:
1765, 1766, 1770, 1771
Total: 13
Miscellaneous (MSC)
Rule
Enforced
Rule Id
Rule
MSC30
Do not use the rand() function for generating pseudorandom numbers
Enforced by CERTCCM:
5022
MSC32
Properly seed pseudorandom number generators
Enforced by CERTCCM:
5031
MSC33
Do not pass invalid data to the asctime() function
Enforced by CERTCCM:
5032
MSC37
Ensure that control never reaches the end of a non-void function
Enforced by DATAFLOW:
2888
MSC38
Do not treat a predefined identifier as an object if it might only be implemented as a macro
Enforced by QAC:
3437, 3475
MSC39
Do not call va_arg() on a va_list that has an indeterminate value
Enforced by QAC:
3497
Page 34


---
*Page 34*

Rule Id
Rule
MSC40
Do not violate constraints
Enforced by QAC:
0232, 0233, 0244, 0268, 0321, 0322, 0338, 0422, 0423, 0426, 0427, 0429, 0430, 0431, 0432, 0435,
0436, 0437, 0446, 0447, 0448, 0449, 0451, 0452, 0453, 0454, 0456, 0457, 0458, 0460, 0461, 0462,
0463, 0466, 0467, 0468, 0469, 0476, 0477, 0478, 0481, 0482, 0483, 0484, 0485, 0486, 0487, 0493,
0494, 0495, 0496, 0497, 0513, 0514, 0515, 0536, 0537, 0540, 0541, 0542, 0546, 0547, 0550, 0554,
0555, 0556, 0557, 0558, 0559, 0560, 0561, 0562, 0563, 0564, 0565, 0580, 0588, 0589, 0590, 0591,
0605, 0616, 0619, 0620, 0621, 0622, 0627, 0628, 0629, 0631, 0638, 0640, 0641, 0642, 0643, 0644,
0645, 0646, 0649, 0650, 0651, 0653, 0655, 0656, 0657, 0659, 0664, 0665, 0669, 0671, 0673, 0674,
0675, 0677, 0682, 0683, 0684, 0685, 0690, 0698, 0699, 0708, 0709, 0736, 0737, 0738, 0746, 0747,
0755, 0756, 0757, 0758, 0766, 0767, 0768, 0774, 0775, 0801, 0802, 0803, 0804, 0811, 0821, 0834,
0835, 0844, 0845, 0851, 0852, 0866, 0873, 0877, 0940, 0941, 0943, 0944, 1023, 1024, 1025, 1033,
1047, 1048, 1050, 1061, 1062, 3236, 3237, 3238, 3244
MSC41
Never hard code sensitive information
Enforced by QAC:
3122
Total: 8
Recommendation
Enforced
Rule Id
Rule
MSC01
Strive for logical completeness
Enforced by QAC:
2000, 2002, 2004
MSC04
Use comments consistently and in a readable fashion
Enforced by QAC:
3108
MSC09
Character encoding: Use subset of ASCII for safety
Enforced by QAC:
0285, 0286, 0287, 0288, 0289, 0299
Page 35


---
*Page 35*

Rule Id
Rule
MSC12
Detect and remove code that has no effect or is never executed
Enforced by DATAFLOW:
2877, 2980, 2981, 2982, 2983, 2984, 2985, 2986
Enforced by QAC:
2008, 2877, 2880, 2881, 2882, 2883, 3110, 3112, 3202, 3203, 3205, 3206, 3207, 3210, 3219, 3229,
3307, 3404, 3422, 3423, 3425, 3426, 3427, 3470
Enforced by RCMA:
1501, 1503
MSC13
Detect and remove unused values
Enforced by DATAFLOW:
2980, 2981, 2982, 2983, 2984, 2985, 2986
Enforced by QAC:
3203, 3205, 3206, 3207, 3229
Enforced by RCMA:
1500, 1502
MSC14
Do not introduce unnecessary platform dependencies
Enforced by QAC:
0202, 0240, 0241, 0242, 0243, 0246, 0284, 0551, 0581, 0601, 0633, 0634, 0635, 0660, 0662, 0830,
0831, 0840, 0899, 1001, 1002, 1003, 1006, 1008, 1012, 1014, 1015, 1016, 1017, 1019, 1020, 1021,
1022, 1026, 1028, 1029, 1034, 1035, 1036, 1037, 1038, 1041, 1042, 1043, 1044, 1045, 1046, 1434,
3664
MSC15
Do not depend on undefined behavior
Enforced by QAC:
0160, 0161, 0162, 0163, 0164, 0165, 0166, 0167, 0168, 0169, 0170, 0171, 0172, 0173, 0174, 0175,
0176, 0177, 0178, 0179, 0184, 0185, 0186, 0190, 0191, 0192, 0193, 0194, 0195, 0196, 0197, 0198,
0199, 0200, 0201, 0203, 0204, 0206, 0207, 0208, 0235, 0275, 0301, 0302, 0304, 0307, 0309, 0323,
0327, 0337, 0400, 0401, 0402, 0403, 0475, 0543, 0544, 0545, 0602, 0603, 0623, 0625, 0626, 0630,
0632, 0636, 0658, 0661, 0667, 0668, 0672, 0676, 0678, 0680, 0706, 0745, 0777, 0779, 0813, 0814,
0821, 0836, 0837, 0848, 0853, 0854, 0864, 0865, 0867, 0872, 0874, 0885, 0887, 0888, 0914, 0915,
0942, 3113, 3114, 3239, 3311, 3312, 3319, 3437, 3438
Enforced by RCMA:
1509, 1510
Page 36


---
*Page 36*

Rule Id
Rule
MSC17
Finish every set of statements associated with a case label with a break statement
Enforced by QAC:
2003
MSC20
Do not use a switch statement to transfer control into a complex block
Enforced by QAC:
2019
Total: 9
POSIX (POS)
Optional Rule
Enforced
Rule Id
Rule
POS30
Use the readlink() function properly
Enforced by CERTCCM:
5033
POS34
Do not call putenv() with a pointer to an automatic variable as the argument
Enforced by CERTCCM:
5024
POS35
Avoid race conditions while checking for the existence of a symbolic link
Enforced by DATAFLOW:
4886, 4887, 4888
POS36
Observe correct revocation order while relinquishing privileges
Enforced by DATAFLOW:
4891, 4892, 4893
POS37
Ensure that privilege relinquishment is successful
Enforced by DATAFLOW:
4876, 4877, 4878
POS38
Beware of race conditions when using fork and file descriptors
Enforced by DATAFLOW:
4951, 4952
Page 37


---
*Page 37*

Rule Id
Rule
POS39
Use the correct byte ordering when transferring data between systems
Enforced by DATAFLOW:
4906, 4907, 4908
POS44
Do not use signals to terminate threads
Enforced by CERTCCM:
5034
POS47
Do not use threads that can be canceled asynchronously
Enforced by CERTCCM:
5035
POS48
Do not unlock or destroy another POSIX thread's mutex
Enforced by DATAFLOW:
4971, 4972, 4981, 4982
POS49
When data must be accessed by multiple threads, provide a mutex and guarantee no adjacent data is
also accessed
Enforced by MTA:
1774, 1775
POS50
Declare objects shared between POSIX threads with appropriate storage durations
Enforced by DATAFLOW:
4926, 4927, 4928
POS51
Avoid deadlock with POSIX threads by locking in predefined order
Enforced by MTA:
1772, 1773
POS52
Do not perform operations that can block while holding a POSIX lock
Enforced by DATAFLOW:
4966, 4967
POS53
Do not use more than one mutex for concurrent waiting operations on a condition variable
Enforced by MTA:
1769
Page 38


---
*Page 38*

Rule Id
Rule
POS54
Detect and handle POSIX library errors
Enforced by QAC:
3200
Total: 16
Rule Enforcement Summary
Total
(a) Total Number of Rules
103
(b) Total Number of 'Not Statically Enforceable' Rules (Assisted/Unassisted)
0
(c) Total Number of Enforceable Rules (a-b)
103
(d) Total Number of Enforced Rules
103
(e) Total Number of Unenforced Rules (c-d)
0
(f) Enforced Rules Percentage (d/c)
100%
(g) Unenforced Rules Percentage (e/c)
0%
Page 39


---
*Page 39*
