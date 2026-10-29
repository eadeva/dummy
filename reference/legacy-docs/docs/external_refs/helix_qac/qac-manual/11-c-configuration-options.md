# C | Configuration Options

C | Configuration Options
-align,-a
Syntax:
-align type=bytes
Default:
-align "char=1" -align "short=2" -align "int=4"
  -align "long=4" -align "longlong=8" -align "float=4"
  -align "double=8" -align "ldouble=8" -align "codeptr=4"
QAC++:
  -align "bool=1" -align "wchar_t=2" -align "default_new=16"
QAC:
  -align "_Bool=1"
Category:
Advanced
Function:
Determines the alignment requirement of each primitive type.
The alignment of data types may be constrained by your  hardware and compiler. For example, your environment may
allocate a char at any memory address, but require an  int to start on a four-byte boundary. Such constraints  impose
restrictions on the validity of pointer  conversions. For example, it might be valid to cast a  pointer to int to a pointer to char
but, invalid to do  the reverse. The analyzer generates warnings that  identify dangerous pointer casts.
See the component manual for details on the product specific alignment options.
Page 172


---
*Page 172*

The available size and alignment values are constrained by the ISO rules on integral size ordering.
Helix QAC for C also uses data type  alignment values to calculate the size of structures. Alignment is  often related to the
size of a data type: see -size,-s.
Type
Size (bits)
Size Rules
Alignment
Min
Default
char
8
8
<=short
1
short
16
16
<=int
2
int
16
32
<=long, <=64 bits
4
long
32
32
<=long long, <=128 bits
4
long long
32
64
<=128 bits
8
float
32
32
<=128 bits
4
double
64
64
<=128 bits
8
Idouble
64
64
<=128 bits
8
codeptr
16
32
<=e.g. int (*)()
4
dataptr
16
32
<=e.g. char *
4
Helix QAC for C++:
bool
8
8
Unspecified
1
wchar_t
16
16
Unspecified
2
Helix QAC for C:
_Bool
8
8
Unspecified
1
-alwayssearchincludedirectoriesfirst,-asidf
Syntax:
-alwayssearchincludedirectoriesfirst[{+|-}]
Default:
-alwayssearchincludedirectoriesfirst-
Category:
Advanced
Function:
When enabled, the search for include directive filenames will start in the include directories before
searching the directory of the including file.
Page 173


---
*Page 173*

Include directories are directories whose paths are  specified via the -i option.
The -alwayssearchincludedirectoriesfirst option affects  the interpretation of include directives whose file path  is enclosed
in double quotes, where by default the  analyzer will search the directory of the including file  before the include
directories.  For include directives  whose file path is enclosed in angle brackets, the  include directories are always
searched before the  directory of the including file.
-arithrsh,-ar
Syntax:
-arithrsh[{+|-}]
Default:
-arithrsh-
Category:
Advanced
Function:
The -arithrsh option defines whether the right shift operator >> performs an arithmetic shift (-arithrsh+) or
a logical shift (-arithrsh-).
The ISO Standard states that the result of an arithmetic  right shift on a negative signed number is  implementation-
defined. That is, each individual  compiler has to specify the effect of shifting negative  values right.
This option is included in the analyzer to support the  general bit-field treatment of data types in the common  dataflow
module.
-prodoption async::safe_functions
Syntax:
-prodoption async::safe_functions=value
Default:
no entry
Category:
Basic
Function:
List the names of functions that are known to be safe to call asynchronously. Any names may be passed
here.
Most functions are not safe to call asynchronously,  i.e. the interruption at any point in execution that a  signal handler can
produce may leave them in a state  where they cannot be safely re-entered. This option  allows a comma-separated list of
functions to be passed,  naming function that are known to be asynchronous-safe  for the code to be analyzed; this is
necessary if the  functions in question are not defined in the current  translation unit.
By default, only the standard C functions  abort, _Exit,  quick_exit and signal are  tagged as asynchronous-safe.
There is no restriction on which functions may be explicitly tagged as safe.
This option will be used by the analyzer, if a listed  function's definition does appear in the translation  unit to be analyzed
and it contains code that would  otherwise be identified as asynchronous-unsafe.
-bitsigned,-bits
Syntax:
-bitsigned[{+|-}]
Page 174


---
*Page 174*

Default:
-bitsigned+
Category:
Advanced
Function:
Defines whether plain integer bit-fields are treated as signed int (-bitsigned+) or unsigned int (-
bitsigned-).
The ISO Standard states that the sign of a bit-field  that is not explicitly signed or unsigned  is implementation-defined.
For Example:

struct
{
  signed int sbit : 3;   /* holds values between -4 and +3       */
  unsigned int ubit : 5; /* holds values between 0 and 31        */
  int bit : 4;           /* may hold values between -8 and +7 or
                            between 0 and 15                     */
} x;

-c17inttypedenumerators,-c17intenum
Syntax:
-c17inttypedenumerators[{+|-}]
Default:
-c17inttypedenumerators-
Category:
Advanced
Function:
Defines whether enum constants unconditionally have the type int.
Page 175


---
*Page 175*

Enumeration constants for an enum type with no underlying type (which is all enum types  until C23) have the type int,
unless a value of a member constant in the  enumeration does not fit in the int type, in which case the behavior in C90
through  C17 is implicitly undefined. From C23, if any member constant in the enumeration  has a value which does not fit
in the int type, all of the constants  in the enumeration take the enumeration's underlying type.
This does not affect enumerations with an explicitly-specified underlying type, which  is a new feature in C23. The
member constants of such enumerations always take the  underlying type.
For Example:

// with -intrinsictype "enum=unsigned long"
// so the underlying type will always go to unsigned long

// all members cleanly fit in int
// so the type of A, B and C is int
enum E1 {
  A = 1,
  B = 2,
  C = 3,
};

// while D fits in int, E does not and F increments
// when -c17inttypedenumerators-, the type of D, E and F is unsigned long
// when -c17inttypedenumerators+, the type of D, E and F is int
//   and the values of E and F are implicitly undefined
enum E2 {
  D = 1,
  E = 3000000000,
  F,
};

Page 176


---
*Page 176*

// the type of G, H and K is unconditionally unsigned short, because
// the explicit underlying type overrides -intrinsictype,
// and there is no need to deduce a type from the values
enum E3 : unsigned short {
  G = 1,
  H = 2,
  K = 3,
};

-c23auto,-c23a
Syntax:
-c23auto[{+|-}]
Default:
-c23auto-
Category:
Advanced
Function:
When enabled, type inference using the auto keyword will be enabled.
Page 177


---
*Page 177*

The 2023 ISO Standard allows declarations using the auto storage-class-specifier  to omit a type-specifier, in which case
the type of the object being declared is inferred  from the initializer.
In earlier language versions this storage-class specifier did nothing, and the object  would be defined with type int when
the type-specifier was omitted.
Additionally, the C23 Standard removed the Constraint that the auto specifier  may only be used at block scope. Using
the auto specifier at file scope is no  longer an error (even if the type is not inferred) when this option is enabled.
This option is off by default until C23 is released.
For Example:

void foo()
{
  // has type int in C17 and earlier, has type float with -c23auto+
  auto x = 1.0f;
}

// File scope: succeeds with -c23auto+
auto int i;

-c23constexpr,-c23cx
Syntax:
-c23constexpr[{+|-}]
Default:
-c23constexpr-
Category:
Advanced
Function:
When enabled, the constexpr keyword will be enabled.
Page 178


---
*Page 178*

The 2023 ISO Standard allows objects to be declared using the constexpr  storage-class-specifier, which allows their
value to be used in any constant  expression context (such as a static assertion, global initializer, or array  designator).
Variables declared with this storage class are still objects with an address,  scope, and lifetime, unlike macros.
This storage class did not exist in previous versions of the language. This  option is off by default in case of code using the
keyword constexpr  as an identifier, as it was a valid identifier in earlier language versions.
For Example:

// at file scope this will have internal linkage
constexpr int K = 10;

// file scope array cannot be variable-length, but this works in C23
int arr[K];

int const * kp = &K; // addressable

-c90nolonglongliterals,-c90noll
Syntax:
-c90nolonglongliterals[{+|-}]
Default:
-c90nolonglongliterals-
Category:
Advanced
Function:
Defines whether type long long will be used for literal constants.
Page 179


---
*Page 179*

The type long long was introduced in C99. In older compilers where the  type did not exist, preprocessing arithmetic
used the long and unsigned  long types instead, and "oversized" decimal integer literals with a value too large  to fit in
the range of long would take the type unsigned long.
This option restores these behaviours, forcing the selection of the type long  in preference to long long for literal
constants.
The type itself will remain available through the long long type specifier.
For Example:

3000000000    // when -c90nolonglongliterals+ is set,
3000000000L   // and 'long' is 32-bit, these will take the type 'unsigned long'

#if 34L + 64U * 3LL   // when -c90nolonglongliterals+ is set,
#endif                // preprocessor arithmetic will evaluate in long,
                      // regardless of suffix

long long x = 0;      // x always has type 'long long'

-coderegex,-cre
Syntax:
-coderegex s/regex/replacement/modifiers
Default:
no entry
Category:
Basic
Function:
When specified, this option can be used to replace sections of code that match a regular expression.
Page 180


---
*Page 180*

Note:
Characters such as single or double quotes,  brackets and '.' have special meaning in regular
expressions.  Depending on the intended meaning of such  characters, standard switching of these
characters may  be required.
When specified, this option can be used to replace  sections of code that match the regular expression.  This may be
particularly useful for:
 n Working around unsupported compiler extensions,
 n Automatically controlling message visibility for auto generated code,
 n Applying custom non-intrusive suppressions.
Optional Modifiers:
The following modifiers are supported:
 n [l] Do not pad replacement expression with newlines
 n [c] Do not pad replacement expression with spaces
Code replacement is particularly useful for handling  non-standard language extensions.  For example, the  __property
extension can be supported using the  following:

```
-coderegex='s/__property([^=]*)=[^;]*;/\1;/'
```

The following source will match the regular expression:

```
__property long var
  = {read = get_Creator};
```

The following tokens will be parsed by the tools:

```
long var;
```

See 'Advanced Topics' in the user manual for more  information (Code Replacement).
-comment,-co
Syntax:
-comment {a|n|i}
Page 181


---
*Page 181*

Default:
-comment n
Category:
Advanced
Function:
Determines how 'comment density metric' is calculated (STCDN).
To calculate this metric, the number of characters in  comments are counted. The analyzer will count characters  from:
 n all comments, (a),
 n all comments except for those from headers, (n),
 n inline or internal comments (i). These are comments within functions and comments that annotate a  line of code
(comments that are on the same line as code at file scope).
-prodoption comment::dynamic_statistics
Syntax:
-prodoption comment::dynamic_statistics[{+|-}]
Default:
-prodoption comment::dynamic_statistics+
Category:
Basic
Function:
This option allows you to control the update behavior of the analysis of commented out code. When the
option is enabled (which it is by default), source token statistics continue to be gathered from the TU
(Translation Unit) under analysis, to improve commented out code detection.
Page 182


---
*Page 182*

In order to generate the analysis of commented out code, an  algorithm is used to compare comments against a table of
"common code sequences" gathered from real-world,  standard-compliant projects. As long as the  "comment::dynamic_
statistics" option is enabled, triplets  are gathered from uncommented sections of the TU being  analyzed, so that unusual
constructions or non-standard  language extensions that appear elsewhere in the TU can be  matched.
For example:

int f (int x, int y) {
  return ({ int w = x + y; w; });  // Statement expressions are a non-standard
extension
}

// This will be recognized as commented out code if, and only if, we
// gather statistics from the current TU
/* return ({ int j = a; j; }); */
// Message only if -po comment::dynamic_statistics+

The option is enabled by default, so that comments can be  matched more accurately against the actual code in use, but
this does mean that changes in one part of a TU may have  unexpected effects on message generation in an apparently
unrelated part of the TU. Disabling the option will ensure  that commented out code detection is determined entirely
locally, so that the same table of "common code sequences"  is used throughout.
-d
Syntax:
-d ident[=[value]]
Default:
no entry
Category:
Basic
Function:
Defines macros for use in parsing.
Page 183


---
*Page 183*

The compilation of source code is often controlled by  macros supplied to the compiler through command line  options.
Macros can be supplied on command line using  -d.  Command line macros can also be undefined using the  -undef
option.
Macros may also be specified using the -systemdefine option.
There are three ways to define a macro:

#define ident 1        /* Command line equivalent: -d ident       */
#define ident value    /* Command line equivalent: -d ident=value */
#define ident          /* Command line equivalent: -d ident=      */

Page 184


---
*Page 184*

Source code often includes constructs that are not part  of the ISO Standard. Compiler vendors frequently  introduce new
keywords in order to extend the  language. To be able to parse these extensions,  Helix QAC for C  provides some special
macros that can be used to help  with supporting 3rd party libraries.
-d ident=_
ignore
ignores the specified identifier and the next token.
-d ident=_
ignore_semi
ignores the identifier and everything up to and  including the next semi-colon (;). However, any  code
in parentheses is excluded from the search,  which means that any semi-colons within the
parentheses are not taken into account.
-d ident=_
ignore_paren
ignores the specified identifier and the following block of code. The block may be of any length and
may be surrounded by (...), [...], or {...}.
-d ident=_
ignore_N
ignores the specified identifier and the next N tokens.
-d ident=_
ignore_
modification
fixes the current replacement list (if any) for  ident.  All subsequent uses of ident with #define
directives will be ignored.  See -rememberfirstdefinedirective,-remfdd.  This option does not apply to
#undef. To avoid the undefinition of a macro, a -coderegex,-cre can be used to remove the directive
completely.
The ignore operation is processed before any other macro substitution takes place.
This option is cumulative, see -forgetall,-forget,-f.
Note:
The value and semantics of macros specified  using -systemdefine,-sd are  identical to those using -d,
however macros specified  with -d are processed before those specified with  -systemdefine.
Note:
_munch. The macro _munch is a deprecated alternative to _ignore.
-prodoption development::scaling
Syntax:
-prodoption development::scaling=value
Default:
-prodoption development::scaling=6000
Category:
Advanced
Function:
Sets the scaling factor between program effort and development time in days
The scaling factor is used in the calculation of the STDEV metric.
See also STDEV Estimated Development (programmer-days).
Page 185


---
*Page 185*

-prodoption df::analyse_header_functions
Syntax:
-prodoption df::analyse_header_functions=[{inter|intra|off}]
Default:
-prodoption df::analyse_header_functions=off
Category:
Advanced
Function:
This option controls how functions defined in header files are analyzed.
When enabled, analysis of functions defined in header  files will take place.  This can result in duplicate  analysis of
functions in each translation unit including  the header file.
See the Dataflow manual for more information.
-prodoption df::function_timeout
Syntax:
-prodoption df::function_timeout=value
Default:
no entry
Category:
Advanced
Function:
Set an aggregate function timeout in milliseconds to limit the overall time spent in dataflow analysis for
each function.
This may curtail related results, and is designed to  avoid lengthy analysis attempts on severely complex  functions.
This option only applies when dataflow is enabled (-enabledataflow+).
This option can be specified both for the Helix QAC for C and/or Helix QAC for C++ components as well as the Dataflow
component.  See the Dataflow manual for more information.
Note:
If a different value is used to configure the Dataflow component compared to the primary analysis
component, then the value configured with the primary analysis component takes precedence.
-prodoption df::struct_last_array_member_size_1
Syntax:
-prodoption df::struct_last_array_member_size_1[{+|-}]
Default:
-prodoption df::struct_last_array_member_size_1-
Category:
Advanced
Function:
Enables checking of single element arrays declared last in a structure.
When enabled, analysis will use the real size of single  element array members declared at the end of a structure
definition.
See the Dataflow manual for more information.
Page 186


---
*Page 186*

-prodoption df::variant_unions
Syntax:
-prodoption df::variant_unions[{+|-}]
Default:
-prodoption df::variant_unions-
Category:
Advanced
Function:
Specifies that unions are used as variant types.
Unions with a large size can be very costly for the SMT solver.  A union that is not used to reinterpret the bits, but as a
variant type,  can be handled as a struct without loss of any analysis precision  thus improving performance.
Type punning through unions is undefined behaviour when this option is enabled.
-prodoption digit_separator::binary_group
Syntax:
-prodoption digit_separator::binary_group=limit
Default:
no entry
Category:
Basic
Function:
Sets the expected length for group of digits in binary literals
If integer literal has any group of digits which is  different length of the specified by this parameters,  then message 4420
will be generated:
 4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::binary_group=4"  to analyze the following code will raise a
message 4420:

const int dl1 = 0b1'0101'1111 ;
const int dl2 = 0b0'10111;                 // expect:4420

-prodoption digit_separator::decimal_group
Syntax:
-prodoption digit_separator::decimal_group=limit
Default:
no entry
Category:
Basic
Page 187


---
*Page 187*

Function:
Sets the expected length for group of digits in decimal literals
If integer literal has any group of digits which is  different length of the specified by this parameters,  then message 4420
will be generated:
 4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::decimal_group=3" to analyze the following code will raise a
message 4420:

const int dl1 = 1'000'000;
const int dl2 = 1'00'000;                 // expect:4420
long unsigned int ui5 = 1'123'123ul;
long unsigned int ui6 = 1'123123ul;     // expect:4420

-prodoption digit_separator::floating_group
Syntax:
-prodoption digit_separator::floating_group=limit
Default:
no entry
Category:
Basic
Function:
Sets the expected length for group of digits in floating part of float literals
Page 188


---
*Page 188*

The floating part belongs the digits before the dot character. For instance:
 n If literal is "1234.32e-10" then the floating part is "1234".
 n If literal is "-12.10F" then the floating part is "12".
If floating part has any group of digits which is different length of the specified by this parameters,  then message 4420 will
be generated:
 4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::floating_group=3" to analyze the following code will raise a
message 4420:

const float dl1 = 1'000'000.5007;
const double dl2 = 100'0.50;                 // expect:4420

-prodoption digit_separator::fractional_group
Syntax:
-prodoption digit_separator::fractional_group=limit
Default:
no entry
Category:
Basic
Function:
Sets the expected length for group of digits in fractional part of float literals
Page 189


---
*Page 189*

The fractional part belongs the digits between the dot character and the exponent (if it exists). For instance:
 n If literal is "1234.32e-10" then the fractional part is "32".
 n If literal is "-12.10F" then the fractional part is "10".
If fractional part has any group of digits which is different length of the specified by this parameters,  then message 4420
will be generated:
 4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::fractional_group=3" to analyze the following code will raise a
message 4420:

const float dl1 = 1000000.500'7;
const double dl2 = 1000.5'007;                 // expect:4420
const float dl3 = 1.500'7e-12F;
const double dl4 = 1000.5'007e10L;             // expect:4420

-prodoption digit_separator::hex_group
Syntax:
-prodoption digit_separator::hex_group=limit
Default:
no entry
Category:
Basic
Function:
Sets the expected length for group of digits in hexadecimal literals
Page 190


---
*Page 190*

If integer literal has any group of digits which is  different length of the specified by this parameters,  then message 4420
will be generated:
 4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::hex_group=4" to analyze the following code will raise a message
4420:

const int dl1 = 0xAB'F16C;
const int dl2 = 0xA'BF16C;                 // expect:4420

-prodoption digit_separator::non_separated_max_size
Syntax:
-prodoption digit_separator::non_separated_max_size=limit
Default:
-prodoption digit_separator::non_separated_max_size=10
Category:
Basic
Function:
Maximum size of numeric literals which don't use separators.
Page 191


---
*Page 191*

Specifies the maximum size for numeric literals that don't use separators. For floating point literals, the max size  is
applied on both the whole and fractional parts individually.
For example, using -po digit_separator::non_separated_max_size=5:


void foo()
{
  100'000'000;  // OK, has separator
  12345;        // OK, not over 5 digits
  1000000;      // expect:4421 Over 5 digits without separator

  0xabcd'1234;  // OK, has separator
  0xd1234;      // OK, not over 5 digits
  0x654321;     // expect:4421 Over 5 digits without separator

  1.123'456;    // OK, whole part not over 5 digits and fractional has separator
  12'456.12345; // OK, whole part has separator and fractional not over 5 digits
  1.234567;     // expect:4421 Fractional part is over 5 digits without separator
  123456.7;     // expect:4421 Whole part is over 5 digits without separator
}


-prodoption digit_separator::octal_group
Syntax:
-prodoption digit_separator::octal_group=limit
Default:
no entry
Category:
Basic
Function:
Sets the expected length for group of digits in octal literals
Page 192


---
*Page 192*

If integer literal has any group of digits which is  different length of the specified by this parameters,  then message 4420
will be generated:
 4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::octal_group=4"  to analyze the following code will raise a message
4420:

const int dl1 = 07'4545;
const int dl2 = 074'545;                   // expect:4420

-echo,-e
Syntax:
-echo text
Default:
no entry
Category:
Advanced
Function:
Specifies that text is echoed to the console.
This option can be used to show the configuration files that are being referenced.
-enabledataflow,-ed
Syntax:
-enabledataflow[{+|-}]
Default:
-enabledataflow-
Category:
Advanced
Function:
Turns on the added dataflow (DF^2) analysis functionality.
The term "dataflow analysis" refers to a range of  techniques in which static analysis of source code is  used to analyze
run-time behavior of a program. Dataflow  analysis can identify a class of problems which may  range from serious issues
such as undefined behavior to  conditions which are of interest simply because they are  frequently associated with coding
errors.
See the Dataflow manual for more information.
-encoding,-en
Syntax:
-encoding encoding
Page 193


---
*Page 193*

Default:
no entry
Category:
Basic
Function:
Specifies the character set of the source file being analyzed.
The analyzer has the ability to read files encoded with  many different character sets.  The name of the  character set to
use for a given file can be specified  using the -encoding option.
Note:
The encoding option is ignored for source  files that use a Byte Order Mark (BOM).  These files  will always
be read using using the UTF variant  specified by the BOM.
The following are examples of supported character set names:
EUC-KR
EUC-JP
GB18030
GBK
ISO-2022-JP
ISO-8859-1
KOI8-U
KOI8-R
Shift_JIS
UTF-8
windows-1252
Note:
Character sets may also have variants not  listed, for example: ISO-8859-14, windows-1250,  UTF-32LE,
etc.
The following special names can also be used:
 n ASC: ASCII encoding, resulting in no input encoding being used.
 n EUC: Japanese Extended Unix Codes.
 n NEWJ: Japanese New JIS encoding.
 n OLDJ: Japanese Old JIS encoding.
 n NECJ: Japanese NEC JIS encoding.
 n SJ: Japanese Shift-JIS encoding.
-errnosettingfunction,-esf
Syntax:
-errnosettingfunction function
Default:
no entry
Category:
Advanced
Function:
Specifies name of the errno-setting function.
Page 194


---
*Page 194*

The function specified by function will be  considered to set errno and so may result  in messages warning that errno has
not been appropriately zeroed or checked.
For example:

void foo(void)
{
  extern void bar (void);
  bar(); // Generates diagnostics with -errnosettingfunction bar
}

-errorstatusreturningfunction,-erf
Syntax:
-errorstatusreturningfunction function
Default:
no entry
Category:
Advanced
Function:
Specifies the name of a function that returns an error status flag.
Page 195


---
*Page 195*

The function specified by function will be  considered to return a value representing a success flag  or error status. If it is
not checked immediately,  a warning will be emitted.
For example:

void foo(void)
{
  extern int bar (void);
  bar(); // Generates a warning with -errorstatusreturningfunction bar

  if (bar () == 0) { } // No warning, error status checked
}

If a number is specified in parentheses immediately  after the name, it is interpreted as the index (starting  from 1) of an
out-parameter which stores error status,  rather than the return value itself:

void foo2(void)
{
  extern void baz (int * status, int value);

  int status1;
  baz (&status1, 42); // Generates a warning with
                      // -errorstatusreturningfunction "baz(1)"

  int status2;
  baz (&status2, 42); // No warning, status2 checked
  if (status2 == 0) { }
Page 196


---
*Page 196*

}

-extensions,-ex
Syntax:
-extensions {ANSIPC, PC, ASM, VMS, C++, TAGLESS, DOLLAR, LONGLONG, ALL}
Default:
no entry
Category:
Advanced
Function:
Specifies the extension class to be used in analysis.
The analyzer supports a variety of compiler extensions  that may be enabled using this option. On the command  line, you
can enable all the extensions by setting the  option to -ex+ or -ex all.
The analyzer recognizes the following extension classes:
 n ansipc: Backslash (\) is permitted within filepaths.
The keywords __near, __far, __huge, __cdecl,  __pascal, and __fortran are recognized and ignored  with a
warning message being issued.
 n PC: The keywords near, far, huge, cdecl,  pascal, and fortran are recognized and ignored,  with a warning
message being issued.
 n asm: Recognizes the assembler code  directives #asm, #endasm and asm("string");. It  enables a number of inline
assembler constructs to  be parsed and ignored.
 n VMS: $ is legal in identifiers.
Filenames appearing in #include directives are mapped to lower case.
 n C++: The reference operator & is recognized in declarations but has no semantic effect.
 n tagless: The names of tag types can be looked up as though they were declared in the  ordinary namespace, as
though they had been declared with a typedef.
 n dollar: $ is legal in identifiers.
Note:
For asm:, please refer to Extension Classes.
-foldplainchar,-fpc
Syntax:
-foldplainchar[{+|-}]
Default:
-foldplainchar-
Category:
Advanced
Page 197


---
*Page 197*

Function:
When enabled, the type 'pointer to char' is treated as semantically equivalent to either type 'pointer to
signed char' or type 'pointer to unsigned char', depending on how the signedness of plain char is
configured with the -unsignedchar option.
The -foldplainchar option operates in conjunction with  the -unsignedchar option.  Although the plain char type  may be
implemented as signed or unsigned, it is  important to understand that it remains a distinct  datatype and is strictly a
different type from either  signed char or unsigned char. This means that even if  plain char is implemented as a signed
type, it is not  legitimate to initialize an array of type signed char  with a literal character string, for example, "ABC". The
only way to achieve this is to apply an explicit cast  (signed char *) to the literal.
This distinction is often considered to be pedantic and  it is seldom observed strictly by compilers. If this  option is set, a
conversion from a "pointer to char" to  either "pointer to unsigned char" or "pointer to signed  char" will not raise the
constraint message 0563 "[C]  Right operand of assignment does not have a compatible  pointer type."
See -unsignedchar,-u
-forceinclude,-fi
Syntax:
-forceinclude filename
Default:
no entry
Category:
Basic
Function:
Causes filename to be implicitly included at the beginning of each translation unit.
This method of "force-including" a file can be sometimes a useful way of defining macros and other project settings.
If the specified filename is not found, then the -i and -si options will be used to search for the file.
-forgetall,-forget,-f
Syntax:
-forgetall option
Default:
no entry
Category:
Advanced
Function:
Resets previous configuration settings for option.
Some options are cumulative in their action in that successive usage of the option adds extra settings rather than
replacing the previous ones.
For example:
 ... -q path1 -q path2 -forgetall q -q path3 filename
For this argument list, the path1 and path2 options will be discarded and only path3 will be quieted.
Page 198


---
*Page 198*

The following options are cumulative in Helix QAC for C:
 n -nomsg,-no,-n
 n -only,-o
 n -quiet,-q
 n -i
 n -systeminclude,-si
 n -d
 n -systemdefine,-sd
 n -warncall,-wc
 n -warnmacroexpansion,-wme
 n -warnset,-ws
-prodoption format::printf
Syntax:
-prodoption format::printf="value"
Default:
-prodoption format::printf="d i o u x X f e E g G c s p n %"
Category:
Advanced
Function:
Specifiers to be supported by 'printf' checking.
Page 199


---
*Page 199*

This option lists the specifiers that are considered  valid in the format string passed to  printf.
For Example:

#include <stdio.h>

void foo (int i)
{
  /*
   * By default a message will be generated on the use of '%z' as a specifier,
   * to indicate that it is not recognized. This behavior can be changed by
   * adding 'z' to the list of valid specifiers.
   */
  printf("%z", 10);
}

-prodoption format::scanf
Syntax:
-prodoption format::scanf="value"
Default:
-prodoption format::scanf="d i o u x X f e E g G c s p n % ["
Category:
Advanced
Function:
Specifiers to be supported by 'scanf' checking.
Page 200


---
*Page 200*

This option lists the specifiers that are considered  valid in the format string passed to scanf.
For Example:

#include <stdio.h>

void foo (int i)
{
  /*
   * By default a message will be generated on the use of '%z' as a specifier,
   * to indicate that it is not recognized. This behavior can be changed by
   * adding 'z' to the list of valid specifiers.
   */
  scanf("%z", &i);
}

-prodoption general::trigger_lines
Syntax:
-prodoption general::trigger_lines=value
Default:
-prodoption general::trigger_lines=50
Category:
Advanced
Function:
Sets the minimum number of significant lines per file
The minimum number of lines required in a file before  thresholds against the STCDN metric are used.
See also STCDN Comment to Code Ratio and -threshold,-thresh.
-help,-h
Syntax:
-help[{+|-}]
Default:
-help-
Category:
Internal
Page 201


---
*Page 201*

Function:
When enabled, a basic help description for the component and its available configuration options is
displayed.
-hidemacrowarnings,-hmw
Syntax:
-hidemacrowarnings[{+|-}]
Default:
-hidemacrowarnings-
Category:
Advanced
Function:
When enabled, warnings generated for code expanded from macros will be hidden.
Messages suppressed as a result of this option will appear as suppressed in display tools.
-prodoption ignore_modification::forceinclude
Syntax:
-prodoption ignore_modification::forceinclude[{+|-}]
Default:
-prodoption ignore_modification::forceinclude+
Category:
Advanced
Function:
When enabled, macros defined in a force included header file will implicitly be defined as _ignore_
modification.
Page 202


---
*Page 202*

A common technique for handling non-standard extensions  is to define the expansion of identifiers to nothing so  they do
not appear in the preprocessed source code.  A  force include header can be used to achieve this:

/* forceinclude.h */
#define __extension__

/* main.cc */
int i = __extension__ 0;

Running with -fi forceinclude.h allows the  code to be parsed successfully.  A slight complication  occurs when the -
rememberfirstdefinedirective option is  disabled.  This can result in user code changing what  the macro expands to and
making invalid the workaround  in the force include header:

/* main.cc */
#define __extension__ __OTHER_EXTENSION__
int i = __extension__ 0;

In order to ensure that the required workaround will  always be used, irrespective of the  -rememberfirstdefinedirective
setting, then the  _ignore_modification feature of -d can be used to fix  the value that the macro expands to:

/* forceinclude.h */
#define __extension__
#define __extension__ _ignore_modification  /* expansion fixed */
#define __extension__ 0                     /* no effect */

When -po ignore_modification::forceinclude is enabled, all macros in the force include file will implicitly be treated as also
being defined with _ignore_modification.
Page 203


---
*Page 203*

See also -forceinclude,-fi, -systemdefine,-sd, -prodoption ignore_modification::systemdefine and -
rememberfirstdefinedirective,-remfdd.
-prodoption ignore_modification::systemdefine
Syntax:
-prodoption ignore_modification::systemdefine[{+|-}]
Default:
-prodoption ignore_modification::systemdefine+
Category:
Advanced
Function:
When enabled, macros defined using -systemdefine (-sd) will implicitly be defined as _ignore_
modification.
A common technique for handling non-standard extensions  is to define the expansion of identifiers to nothing so  they do
not appear in the preprocessed source code:

/* main.cc */
int i = __extension__ 0;

Running with -systemdefine "__extension__="  allows the code to be parsed successfully.  A slight  complication
occurs when -rememberfirstdefinedirective  option is disabled.  This can result in user code  changing what the macro
expands to and making invalid  the workaround in the force include header:

/* main.cc */
#define __extension__ __OTHER_EXTENSION__
int i = __extension__ 0;

In order to ensure that the required workaround will  always be used, irrespective of the  -rememberfirstdefinedirective
setting, then the  _ignore_modification feature of -d and -sd can be used  to fix the value to which the macro expands:  -
systemdefine "__extension__=" -systemdefine  "__extension__=_ignore_modification" .
When -po ignore_modification::systemdefine is enabled,  all macros specified using -systemdefine (-sd) will  implicitly be
treated as also being defined with  _ignore_modification.
See also _ignore_modification in -d,  -rememberfirstdefinedirective,-remfdd and  -prodoption ignore_
modification::forceinclude.
Page 204


---
*Page 204*

-i
Syntax:
-i path
Default:
no entry
Category:
Basic
Function:
Specifies a search path for header files.
This option is cumulative, see -forgetall,-forget,-f.
Note:
Directories specified with -i will be searched before directories specified with -systeminclude,-si.
-indentlevel,-il
Syntax:
-indentlevel value
Default:
-indentlevel 0
Category:
Advanced
Function:
Specifies the amount of space used to indent code.
Message 2215 will be issued if the code indentation differs from this value.  With the value set to zero (default), the
analyzer will not enforce a  specific indentation depth, but it will identify inconsistent indentation  and will issue message
2201.
-intrinsictype,-it
Syntax:
-intrinsictype {size_t | ptrdiff_t | wchar_t | enum}=datatype
Default:
-intrinsictype "size_t=unsigned int"
  -intrinsictype "ptrdiff_t=long"
  -intrinsictype "wchar_t=unsigned char"
  -intrinsictype "enum=signed int, unsigned int, signed long, unsigned long, signed long long,
unsigned long long"
Category:
Advanced
Function:
Determines the underlying type and semantics of built-in types during parsing.
Determines the type associated with the sizeof operator (size_t), the result of pointer subtraction (ptrdiff_t) and the
underlying type to use for enumerations.  Allows wchar_t to be modelled as an alias to a type rather than a keyword and a
distinct type.
Page 205


---
*Page 205*

For -intrinsictype "size_t=...", -intrinsictype  "ptrdiff_t=...", and -intrinsictype "wchar_t=...", a  single built-in type name is
specified to use as the  underlying type. Helix QAC for C will generate a level 9  warning if these are not consistent with
any typedef  settings encountered in the source code.
For -intrinsictype "enum=...", a sequence of basic data  types is specified in a comma-separated list. For each  enum
definition, Helix QAC for C determines the minimum  and maximum value of the enumerators used to define the  enum
type. Starting with the first entry in this list,  the first type large enough to hold all the enum's  values will be selected as the
underlying type.
This option also allows user-defined types to be marked as  suitable for use in implementation-defined contexts:
For -intrinsictype "bool=...", a sequence of typedefs or  enumeration names is specified in a comma-separated  list. Each
specified type name will be treated as  essentially Boolean by Helix QAC for C. Accepted types are:
 n an enum with exactly 2 enumerators of which one is equal to 0.
 n a typedef to a numeric type.
For -intrinsictype "bitfield=...", a sequence of built-in type names is specified in a comma-separated list.  The keyword
'enum' may also be specified here. Each specified type will be marked as suitable for use in bitfield declarations.  If no
signedness is specified, both signed and unsigned versions of the type may be used; otherwise, only the specified
signedness is marked as suitable.
-k+r
Syntax:
-k+r sun, a, b, c, e, g, i, l, n, p, s, t, u, v, x
Default:
no entry
Category:
Advanced
Function:
Identifies ISO language features that should be avoided if using a K&R compiler.
Page 206


---
*Page 206*

If you want your code to be compliant with K&R  standards, you will need to restrict your usage of the C  language to
exclude all these features.
Specifying a construct with this option will generate  one of the K&R messages when the analyzer encounters  that
construct. If your code does not need to be  compatible with pre-ISO standards, do not set this  option.
The following options can be specified in any order:
 n sun: enforces compatibility with the Sun K&R cc compiler under SunOS 4.1 or earlier. This is equivalent to: -k+r
acegipstux.
 n a: initializing locally-declared structures and unions.
 n b: bit-field
 n c: string concatenation
 n e: #error
 n g: glue operator ##
 n i: signed keyword
 n l: #elif
 n n: enumerated types
 n p: function prototypes
 n s: stringify operator #
 n t: const and volatile
 n u: unary +
 n v: void keyword
 n x: Initializing extern variables.
-list
Syntax:
-list filename
Default:
no entry
Category:
Internal
Function:
Used to specify a file list containing the source files and their output paths that are to be included in the
analysis.
-maxerrors,-maxerr
Syntax:
-maxerrors value
Default:
-maxerrors 0
Category:
Advanced
Page 207


---
*Page 207*

Function:
Determines the number of hard errors that will cause the analysis to stop.
The default of zero indicates that the parser will  attempt to continue to completion regardless of hard  errors encountered.
The parser will issue return code 1 when any hard errors  are encountered. This setting merely decides whether  parsing
will continue to source completion.
-maxlinelength,-mll
Syntax:
-maxlinelength value
Default:
-maxlinelength 0
Category:
Advanced
Function:
Specifies the maximum physical line length in the source code, before the line-splicing phase of
translation.
For a non zero positive value, the length of each source  line is checked to ensure that it is less than the  specified value.
When set to zero no checking is  performed.
-maxmacrohistory,-maxmh
Syntax:
-maxmacrohistory value
Default:
-maxmacrohistory 8192
Category:
Advanced
Function:
Limit on the number of entries to store in the macro expansion history of a source location.
Page 208


---
*Page 208*

By default, history information is stored for tokens expanded from macros in order to  provide better location reporting and
to perform some analyses of library objects defined  as macros. However, this can use up a lot of storage if macros are
heavily used to create  nested expansions.
Only the specified number of history entries will be stored. If macro expansion is more  deeply nested, preprocessing
itself will not be affected, but the "expanded from here"  history will not be available for error reporting. Some analyses
that check whether an  expression originates from a macro may fail to work if the expression is produced at an
unrecorded level of nesting.
If zero is the value specified, no macro history will be recorded at all. This may be  useful for some machine-generated
files. The value is always zero for expansions originating  in quieted headers.
This limit can also be adjusted within a file by means of the  PRQA_MAX_MACRO_HISTORY pragma.  This may be useful
when a certain section within a TU uses deep nesting.

#define D NULL
#define C D
#define B C
#define A B

void * p1 = A;    // if -maxmacrohistory is less than 5, this will be seen as '=
0'
void * p2 = NULL; // if -maxmacrohistory is zero, this will be seen as '= 0'

// set the macro history length limit to 3, regardless of previous options
#pragma PRQA_MAX_MACRO_HISTORY 3
// change the macro history length limit to 8
#pragma PRQA_MAX_MACRO_HISTORY 8

-prodoption metrics::no_do_while
Syntax:
-prodoption metrics::no_do_while[{+|-}]
Default:
-prodoption metrics::no_do_while+
Category:
Basic
Page 209


---
*Page 209*

Function:
Controls whether do..while loops with an integer constant zero loop condition are counted as control
structures.
A do..while loop with a constant zero as the loop controlling expression will only be executed once and is  generally
similar to a simple braced compound expression. It does not introduce algorithmic complexity and  is normally introduced
by macros purely for block scope purposes. Therefore, it is not counted as part of  control flow metrics by default.
Loops that make use of a break or continue statement will still be counted as  their loop structure is relevant.
-namelength,-na
Syntax:
-namelength value
Default:
-namelength 63
Category:
Advanced
Function:
Determines the number of characters in valid internal and preprocessing identifiers.
Message number 0779 will be issued for each internal  identifier encountered that is not distinct within the  number of
characters specified.
Message number 0787 will be issued for each preprocessing  identifier encountered that is not distinct within the  number
of characters specified.
The ISO Standard states that compilers should treat at  least the first 31 characters of internal identifiers  and macro
names as significant.  Some implementations may distinguish them  in more than 31 characters but it is not advisable to
depend on this extension.
Programming standards may choose to restrict the  declaration of identifiers so that they are distinct  within a smaller
number of characters.
See also -prepronamelength,-ppna.
-namerulefile,-nrf
Syntax:
-namerulefile filename
Default:
no entry
Category:
Basic
Function:
Specifies the file containing the naming convention rules to be applied by namecheck.
The name rules file contains the rules to be used by the  Name Checker. As a minimum, each rule should specify the
pattern (Regular Expression) that is to be applied to  each type of identifier (macros, functions, typedefs,  variables, etc).
You can have different rules for  different types of identifier.
See the Configuration File section of the Namecheck user manual.
Page 210


---
*Page 210*

-nomsg,-no,-n
Syntax:
-nomsg message_number_list
Default:
no entry
Category:
Non-component
Function:
Suppresses the display and generation of the specified messages.
Message numbers can be specified individually, or as a  list, range or a combination of both:
 n -nomsg 2356
 n -nomsg 1234,1236,1240
 n -nomsg 2111,2200-2300
Note:
This option is only available at the file or directory level.  The enabling or disabling of diagnostics at the
component level is managed through the Rule Configuration File (RCF).
This option is cumulative.  See -forgetall,-forget,-f.
If upgrading from a version of Helix QAC for C earlier than 8.0, see the Dataflow manual for more information.
-only,-o
Syntax:
-only message_number_list
Default:
no entry
Category:
Non-component
Function:
Only the specified warning messages will be generated.
Message numbers can be specified individually, or as a  list, range or a combination of both:
 n -only 2356
 n -only 1234,1236,1240
 n -only 2111,2200-2300
Note:
This option is only available at the file or directory level.  The enabling or disabling of diagnostics at the
component level is managed through the Rule Configuration File (RCF).
This option is cumulative. See -forgetall,-forget,-f.
If upgrading from a version of Helix QAC for C earlier than 8.0 then see the Dataflow manual for more information.
Page 211


---
*Page 211*

-outputpath,-op
Syntax:
-outputpath path
Default:
no entry
Category:
Internal
Function:
Determines the path to which all output files will be generated during analysis, and, by extension, the
location from which all files will be read as the input for RCMA analysis.
See the "Analyzing Source Code" section of the Helix QAC for C or Helix QAC for C++ user manual, as appropriate.
-ppfilename,-ppf
Syntax:
-ppfilename[{+|-}]
Default:
-ppfilename-
Category:
Advanced
Function:
When enabled, comments are introduced into the preprocessed file which indicate the source file and
line number from which the code was derived.
This option only applies when generating preprocessed output, enabled using -pplist.
See -pplist,-ppl.
-pplist,-ppl
Syntax:
-pplist[{+|-}]
Default:
-pplist-
Category:
Advanced
Function:
When enabled, a preprocessed file is generated in the output directory with a .i file extension.
-ppmetrics,-ppm
Syntax:
-ppmetrics[{+|-}]
Default:
-ppmetrics-
Category:
Advanced
Function:
This option is designed to be used with file metrics, and governs the inclusion of header file information
in the calculation of metrics.
Page 212


---
*Page 212*

 n -ppmetrics+ results in all code/tokens in included header files being used when calculating metrics.
 n -ppmetrics- results in code/tokens in included header files being ignored when calculating metrics.
-pponly,-ppo
Syntax:
-pponly[{+|-}]
Default:
-pponly-
Category:
Advanced
Function:
When enabled, analysis will stop after preprocessing.
Output files will only contain information generated  from the preprocessing stage:
 n file metrics,
 n implicit declarations,
 n macros, and
 n preprocessor messages.
This option can be used for analysis debug purposes,  specifically to determine that preprocessing completes  without
engaging in C++ parsing and analysis.
Note:
When this option is enabled, Helix QAC for C will not evaluate sizeof expressions used in #if directives.
-prepronamelength,-ppna
Syntax:
-prepronamelength value
Default:
-prepronamelength 63
Category:
Advanced
Function:
Determines the number of characters in valid preprocessing identifiers separately from internal
identifiers.
Message number 0787 will be issued for each preprocessing  identifier encountered that is not distinct within the  number
of characters specified.
The ISO Standard states that compilers should treat at  least the first 31 characters of internal identifiers  and macro
names as significant.  Some implementations may distinguish them  in more than 31 characters but it is not advisable to
depend on this extension.
Programming standards may choose to restrict the  declaration of identifiers so that they are distinct  within a smaller
number of characters.
This option will override the value passed to -namelength  if specified, to allow for separate implementation limits in the
preprocessor and the C compiler. If this option is not specified,  the value of -namelength will be used instead.
See also -namelength,-na.
Page 213


---
*Page 213*

-prodoption,-paloption,-qacppoption,-qo,-po
Syntax:
-prodoption argument
Default:
no entry
Category:
Advanced
Function:
Enables fine-grained configuration of analysis.
prodoption is used to provide additional fine-grained configuration to the analysis performed by a component.
-prodoption qax::limit
Syntax:
-prodoption qax::limit=size(KB)
Default:
-prodoption qax::limit=30
Category:
Advanced
Function:
Sets the maximum packet size in KB sent to the QAX daemon.
The following information is sent by the analysis tools to the QAX daemon:
 n Filenames
 n Locations
 n Preprocessor Events
 n Diagnostics
 n Annotations
 n Function Flow Graphs.
This option controls the amount of data stored before  being transmitted to the server.
In general this option does not need to be changed,  however, if investigating a failure with the tool, it  can be useful to set
the option to 0 in order that all  data is sent immediately to the daemon.
-quiet,-q
Syntax:
-quiet filename|path
Default:
no entry
Category:
Basic
Function:
Suppresses the generation of diagnostic and metrics output for the specified file or files in the specified
path.
Page 214


---
*Page 214*

This will have the effect of suppressing warning  messages as well as significantly reducing the size of  the output
produced.
Note:
This option applies only to included files and has no effect on the main source file.
Note:
This option should not be used for project header files or directories, as it may affect the results of CMA,
Project Metrics and Reports.
This option is cumulative, see -forgetall,-forget,-f.
-quietextended,-qx
Syntax:
-quietextended filename|path
Default:
no entry
Category:
Basic
Function:
Suppresses the generation of diagnostic output for unused contents of the specified file or files in the
specified path.
This will have the effect of suppressing warning  messages as well as significantly reducing the size of  the output
produced.  This suppression is limited to constructs from those files/folders  that are not used in non suppressed files.
When the argument is a non-absolute path, the path is interpreted to be a regular file  path relative to a -systeminclude
path. If the concatenation of a system include path  and the relative file path corresponds to an existing file, the option
takes effect on that file.
Note:
This option applies only to included files and has no effect on the main source file.
This option is cumulative, see -forgetall,-forget,-f.
-randomnumbergeneratorseed,-rngs
Syntax:
-randomnumbergeneratorseed function(argIndex)
Default:
no entry
Category:
Advanced
Function:
Specifies how a random number generator (RNG) is initialised with a new seed.
Page 215


---
*Page 215*

The argument to this option should be a mangled name referring to a function followed  immediately by a number in
parentheses.
The specified function will be treated as a function that initialises a RNG.
The number specified in parentheses immediately  after the name, is interpreted as the index (starting  from 1) of the
parameter which contains the new seed  being used to configure the RNG.
It is the value of the seed parameter that is analysed to see if it is  unchanging or predictable.
For example:

const int SEED=1;
void foo(void)
{
  Random_Init(SEED);  // Generates diagnostics with -rngs="Random_Init(1)"
}

In C++, the mangled name can be used to limit the match to a member or single overloaded function.

struct SeedCtx
{
  void init(int);
};

int SEED = 1;
void foo(void)
{
  SeedCtx rng;

  rng.init(SEED);   // generates diagnostics with -rngs=".QN7SeedCtxN4initPi(1)"
Page 216


---
*Page 216*

}


-remark,-rem
Syntax:
-remark comment
Default:
no entry
Category:
Advanced
Function:
The -remark option can be used to add additional comments into configuration files. Alternatively,
comments can be included in the configuration files by prefixing the comments with an asterisk.
-rememberfirstdefinedirective,-remfdd
Syntax:
-rememberfirstdefinedirective[{+|-}]
Default:
-rememberfirstdefinedirective+
Category:
Advanced
Function:
When enabled, a redefinition using a #define directive will not change the replacement list of the macro.
Page 217


---
*Page 217*

The default behavior of the analyzer is to issue a  message and update the replacement list of a macro for  each new
#define directive:

#define A 1     /* A's replacement list set to 1 */
#define A 2     /* Message generated to highlight that macro A has been
                /* redefined and A's replacement list changed to 2 */

int i = A;      /* A expands to 2 */

Previous versions operated slightly differently in that  a message was issued but the replacement list was not  changed:

#define A 1     /* A's replacement list set to 1 */
#define A 2     /* Message generated to highlight that macro A has been
                /* redefined and A's replacement list unchanged as 1 */

int i = A;      /* A expands to 1 */

The -rememberfirstdefinedirective option can be used to  revert the behavior to match the previous functionality.
Note:
Macros defined on the command line always use the last value.
See also _ignore_modification in -d,  -systemdefine,-sd,  -prodoption ignore_modification::systemdefine and  -prodoption
ignore_modification::forceinclude.
-settings,-set
Syntax:
-settings[{+|-}]
Default:
-settings-
Category:
Internal
Function:
Print the settings used by the tool after the complete processing of all command line arguments.
Page 218


---
*Page 218*

When enabled, the current values for all configuration options are listed to the standard output.
-size,-s
Syntax:
-size type=bits
Default:
-size "char=8" -size "short=16" -size "int=32
  -size "long=32" -size "longlong=64" -size "float=32"
  -size "double=64" -size "ldouble=128" -size "codeptr=32"
QAC++:
  -size "bool=8" -size "wchar_t=16"
QAC:
  -size "_Bool=8"
Category:
Advanced
Function:
Defines the type sizes (measured in bits) implemented in your compiler environment.
The analyzer uses type size values to calculate the size  of structures and to perform analysis.
The available size and alignment values are constrained  by the ISO Standard rules on integral size ordering. The  size is
often related to the alignment of a data type.
See -align,-a for the full set of constraints on size and alignment.
-skippragma,-spragma
Syntax:
-skippragma pragma_start,pragma_end
Default:
no entry
Category:
Advanced
Function:
Defines the behavior of #pragma directives.
Page 219


---
*Page 219*

#pragma statements are preprocessor directives that are  specific to a particular compiler. By default, when a  #pragma is
encountered, message 3116 will be generated.
You can declare a #pragma or a #pragma block by  specifying #pragma names.  The following syntax is  supported:

/* Command Line:  -skippragma ID */
#pragma ID   /* This pragma is ignored */

/* Command Line:  -skippragma X1,X2 */
#pragma x1   /* This pragma and all code lines up to and
                including the #pragma x2 are ignored */

#pragma x2

/* Command Line:  -skippragma ABC* */
#pragma ABC1   /* This pragma ignored*/
#pragma ABC2   /* This pragma ignored*/
#pragma ABC3   /* This pragma ignored*/

Note:
The analyzer also recognizes the specific  #pragma directives of its own, for example,  PRQA_
MESSAGES_OFF and PRQA_MESSAGES_ON. These do not  need to be configured. They are used for
suppressing and  re-enabling warning messages from within the code. Refer  to Message Suppression in
the component manual.
-slashwhite,-sl
Syntax:
-slashwhite[{+|-}]
Default:
-slashwhite-
Category:
Advanced
Function:
When enabled, parsing ignores whitespace between \ and the end of a line.
Page 220


---
*Page 220*

Some source code uses continuation lines that have  whitespace between the \ and the end of the line. This  can happen
when source files are transferred between  different operating systems and results in errors,  unless this option is enabled.

-stoponerror,-soe
Syntax:
-stoponerror[{+|-}]
Default:
-stoponerror-
Category:
Advanced
Function:
Causes the analysis to stop on the first hard error.
If enabled, analysis will stop on the first hard error encountered.
This is disabled by default, which means that the parser will continue to  completion regardless of any hard errors
encountered.
-strictrank,-sr
Syntax:
-strictrank[{+|-}]
Default:
-strictrank-
Category:
Advanced
Function:
The -strictrank option affects the behavior of implicit type conversion messages which report
conversions from one integer type to a type of the same signedness but lower rank.  These messages
are referred to in the standard message file as 'narrowing' conversions.
When the strictrank option is off (-strictrank-), these  messages are not generated when converting to a type  which is of
lower rank but is actually an "equivalent"  type.
The term rank (integer conversion rank) is a term used  in the C99 ISO Standard to describe the intrinsic  ordering of
integer types. In brief, no two integer  types have the same rank even if they share the same  representation. Type long (or
long long) has the highest  rank and type _Bool has the lowest rank. The rank  of an unsigned type is equal to the rank of
the  corresponding signed type.
Equivalent type in this context refers to the situation  where two integer types are of different integer rank  but share the
same representation.
-strictsignedness,-ss
Syntax:
-strictsignedness[{+|-}]
Default:
-strictsignedness+
Category:
Advanced
Function:
Generate unsigned to larger signed messages for wider types.
Page 221


---
*Page 221*

This option is obsolete: it has no effect on the  'Essential Type' Arithmetic Type messages. It is  effectively always on to
enforce the Essential Type  system. The range of "Unsigned to Larger Signed"  messages has been replaced with a single
message 4443.
The messages that were affected by this option are in  Obsolete Messages: Arithmetic Type - Implicit  Conversions.
-style,-sty
Syntax:
-style {k+r|exdented|indented}
Default:
-style exdented
Category:
Advanced
Function:
Enforces various bracing styles.
The following are the three styles of bracing and  indentation most commonly used in C programming:

// Indented
if ( )
  {
  ...
  }
// Exdented
if ( )
{
  ...
}
// K&R (Kernighan & Ritchie)
if ( ) {
  ...
}

The analyzer will enforce consistency, but it will not  enforce any particular depth of indentation, unless that  is specified by
using the -indentlevel option.
Page 222


---
*Page 222*

-systemdefine,-sd
Syntax:
-systemdefine ident[=[value]]
Default:
no entry
Category:
Basic
Function:
Defines system macros.
System macros in the analyzer have the same value and  semantics as -d except that they  are processed after the -d
options.
This option is cumulative, see -forgetall,-forget,-f.
See the -d option for information on replacement lists with special meaning.
-systeminclude,-si
Syntax:
-systeminclude path
Default:
no entry
Category:
Basic
Function:
Specifies a search path for your system header files.
Directories specified with the -systeminclude option  have the same value and semantics as those specified  using -i,
except that these  directories will be searched after the  directories specified with -i.
This option is cumulative, see -forgetall,-forget,-f.
-tabstop,-tab,-t
Syntax:
-tabstop columns
Default:
-tabstop 8
Category:
Advanced
Function:
Specifies the number of spaces represented by a tab character.
Tab spacing is not related to the depth of indentation.  It does affect the column location used when issuing  diagnostics
against the source file.
-thirdparty,-tp
Syntax:
-thirdparty[{+|-}]
Default:
-thirdparty-
Category:
Non-component
Page 223


---
*Page 223*

Function:
Specifies a file or folder as third party.
This option is used by QA Framework to support 3rd Party source code. See QA Framework manual for more information
about this option.
-threshold,-thresh
Syntax:
-threshold metric{<|<=|=|>|>=}value[:[prefix_]msg_no]
Default:
no entry
Category:
Advanced
Function:
When specified, message msg_no is output whenever the threshold condition (from the set
{<|<=|=|>|>=} for specified metric is exceeded.
The metric is specified by the name that appears in the metrics  records of the .arc file. There are no default  values. If
 :msg_no is omitted the default analyzer message  4700 will be used.
The optional prefix_ can be used to specify the  Compliance Module that msg_no is associated with.
See Metric Thresholds  and Metric Output File for more information.
See Metric Thresholds and Metric Output File sections of the Helix QAC for C/C++ component manuals for more
information.
-undef
Syntax:
-undef ident
Default:
no entry
Category:
Basic
Function:
Will undefine, if any, a macro ident previously specified on the command line
The -undef option when specified will causes the removal  of definitions of ident previously seen on the  command line.
For example if the sequence:
 -d "A=1" -d "B=2" -d "c=3" -undef B
Will have the same affects as:
 -d "A=1" -d "c=3"
The -undef option applies to both the  -d and -systemdefine,-sd  options equally, and so entries in both lists will be affected
by the option.
For example if the sequence results in no macros being  processed by Helix QAC for C:
 -d "A=1" -sd "B=2" -undef B -undef B
See the -d option for information on replacement lists with special meaning.
Page 224


---
*Page 224*

-unsignedchar,-u
Syntax:
-unsignedchar[{+|-}]
Default:
-unsignedchar-
Category:
Advanced
Function:
When enabled, the plain char datatype is interpreted as unsigned char.  When disabled, -unsignedchar-,
it is interpreted as signed char.
The ISO Standard states that a compiler may implement  char as a signed or unsigned datatype. It is safer not  to assume
any particular implementation.
You can test whether your source relies on plain char  being treated in a particular manner by compiling and  running the
following program:

#include <stdio.h>

int main ()
{
  char c = 130;
  printf("'%d'\n", c);
}

If the output of the program is a negative number then  plain char has a signed type.  Otherwise it has an  unsigned type.
Note:
Some compilers have an option to switch  their behavior between signed and unsigned.  It is  therefore
important to compile the above program with  the same settings as are being used in the target  project.
-url
Syntax:
-url url
Default:
no entry
Category:
Internal
Function:
The URL of the server to which analysis data should be sent.
Page 225


---
*Page 225*

If no -url is specified, then output will be sent to the legacy output formats.
-version,-ver,-v
Syntax:
-version[{+|-}]
Default:
-version-
Category:
Internal
Function:
When enabled, the version number is printed to standard out and the tool will exit immediately.
-via
Syntax:
-via file
Default:
no entry
Category:
Advanced
Function:
Used to specify a file containing additional configuration options.
-virtualmemorylimit,-vml
Syntax:
-virtualmemorylimit value
Default:
-virtualmemorylimit 70
Category:
Advanced
Function:
Determines the limit on the available memory a component can utilise.
Before analysis is performed by a component a limit is set on  the amount of memory that the component can utilise. By
default this limit  is set to either a percentage of the systems physical memory or  a default fixed size, whichever is largest.
This option determines the limit placed on the memory available to  the component during analysis as a percentage of the
total systems memory.
If the argument of this option is 0 then no memory limit is applied to the component.  And if the value of the argument does
not lie between 0 and 100 then the default limit  will be applied.
-warncall,-wc
Syntax:
-warncall function[=[prefix_]msg_no]
Default:
no entry
Category:
Advanced
Page 226


---
*Page 226*

Function:
Displays warning message msg_no if a call to function is encountered.
If no message number is specified for C, the following default message  is displayed:
 2010 The function 'func_name' must not be called.
If no message number is specified for C++, the following default message  is displayed:
 3999 Function 'func_name' called.
When msg_no is specified, the optional prefix_  can be used to specify the Compliance Module that msg_no is
associated with.
This option is cumulative, see -forgetall,-forget,-f.
-warnmacroexpansion,-wme
Syntax:
-warnmacroexpansion macro[=[prefix_]msg_no]
Default:
no entry
Category:
Advanced
Function:
Displays warning message msg_no if a macro is expanded.
If no message number is declared, the following message  is displayed:
 1007 The macro 'macro_name' must not be expanded.
This option ignores any message number which is not  between 1 and 9998 inclusive.
When msg_no is specified, the optional prefix_  can be used to specify the Compliance Module that msg_no is
associated with.
This option is cumulative, see -forgetall,-forget,-f.
-warnset,-ws
Syntax:
-warnset qualified_member_name[=[prefix_]implicit_msg_no[!filter_value],explicit_const_msg_no
[!filter_value],explicit_nonconst_msg_no]
Default:
no entry
Category:
Advanced
Function:
Displays a warning if qualified_member_name is set. Which warning is displayed depends on context
(see below for details).
Page 227


---
*Page 227*

Note: in C++ the qualified_member_name must be specified using the mangled name format.
If no message number is specified for C, the following default message is displayed:
 2033 The member 'member_name' must not be set.
If no message number is specified for C++, the following default message is displayed:
 3998 Member variable 'member_name' modified.
Warning Messages and Context
Each -warnset may specify up to three warning messages per fully qualified member name.
The first is the message to be raised if the member is set "implicitly". For example,  if the non-static data member has a
default value, and no other value is provided during  construction of an object, the implicit_msg_no will be raised.

// QAC  : -warnset A::value -warnset A::seed=5001
// QAC++: -warnset .QNAN5value -warnset .QNAN4seed=5001

struct A
{
  int value =  1;            // default message raised
  int seed = 1;              // 5001 raised
};

Page 228


---
*Page 228*

The second is the message to be raised if the member is explicitly set to a compile-time constant  value (i.e. a value which
does not change between program runs). For example: passing a literal value  to a member during construction will result
in the explicit_const_msg_no being raised.

// QAC  : -warnset A::value -warnset A::seed=5001,5002
// QAC++: -warnset .QNAN5value -warnset .QNAN4seed=5001,5002

typedef struct
{
  int value;
  int seed;
} A;

A a {0,     // default raised
     0};    // 5002 raised

Page 229


---
*Page 229*

Finally, the third is the message to be raised if the member is explicitly set to a dynamic value  (i.e. a value that is different
every time the program runs). For example: passing the return value  of a function call to a member during construction
will result in the explicit_nonconst_msg_no being raised.

// QAC  : -warnset A::value -warnset A::seed=5001,5002,5003
// QAC++: -warnset .QNAN5value -warnset .QNAN4seed=5001,5002,5003

typedef struct
{
  unsigned value;
  unsigned seed;
} A;

unsigned getInitValue();
unsigned getInitSeed();

A a {getInitValue(),    // default raised
     getInitSeed()};    // 5003 raised

If at least one message number is specified but not all the messages are specified, then  any that are unspecified will be
ignored.
!filtervalue
The first two msg_no values can optionally take a "filter value". In the 2021.3 release this is an  integer value that
represents a single "valid" integer value. If analysis detects that the member is  being to set to anything other than the
"filter value" then the associated msg_no will be raised.
Page 230


---
*Page 230*

The command line uses "!" to specify "not <filter_value>". The associated msg_no will be raised if  qualified_member_
name is set to a value that is not <filter_value>.

// QAC  : -warnset A::value=5001!1,5002!1,5003
// QAC++: -warnset .QNAN5value=5001!1,5002!1,5003

typedef struct
{
  unsigned value = 0;  // 5001 raised
} A;

A a_bad {128};  // 5002 raised
A a_ok  {1};    // 5002 NOT raised

When at least one message number is specified, the optional  prefix_ can be used to specify the Compliance Module
that all messages are associated with.
This option is cumulative, see -forgetall,-forget,-f.
-xcase,-xc
Syntax:
-xcase[{+|-}]
Default:
-xcase-
Category:
Advanced
Function:
Specifies if the case of external identifiers can be ignored.
The C90 ISO Standard allows an implementation to ignore  alphabetical case in external identifiers. When -xcase  is
enabled, this restriction is strictly imposed.
See -xnamelength,-xn for  implications of external identifier significance.
-xnamelength,-xn
Syntax:
-xnamelength value
Default:
-xnamelength 31
Page 231


---
*Page 231*

Category:
Advanced
Function:
Specifies the number of significant characters in an external identifier.
The C90 ISO Standard states that an implementation may  restrict the significance of an external name to only 6
characters and may ignore alphabetical case. This is  quite severe and many compilers and linkers relax this  restriction.
Message number 0777 will be generated for each external  identifier it encounters that is not distinct within the  number of
characters you specified.
Page 232


---
*Page 232*
