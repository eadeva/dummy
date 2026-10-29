# 3 | Helix QAC for C Configuration

3 | Helix QAC for C Configuration
Configuring  Helix QAC for C
One of the strengths of  Helix QAC for C is its high degree of configurability. Configuration options are defined in the
Analysis tab of Helix QAC’s Project Properties, and are passed to the  Helix QAC for C application as command line
arguments. The options can be grouped based on:
 n Compiler Selection
 n Type of Analysis
 n Diagnostic Suppression
Compiler Selection
These options are used by  Helix QAC for C to match the behaviour of your compiler:
Option
Effect
Data Types - Interpretation
-bitsigned
Whether plain integer bit-fields are treated as signed or
unsigned int
-unsignedchar
Whether plain char is treated as signed or unsigned char
-foldplainchar
Whether pointer to char is treated as pointer to signed or
unsigned char
-arithrsh
Whether the right shift operator performs an arithmetic shift
or a logical shift
-intrinsictype
Underlying types associated with intrinsic types size_t,
ptrdiff_t, and wchar_t
Data Types - Size and Alignment
-align
The alignment of each primitive C type
-size
The type sizes (measured in bits) implemented in your
compiler environment
Extensions
-forceinclude
Implicitly include the specified file at the beginning of each
file
Page 16


---
*Page 16*

Option
Effect
-extensions
The compiler extensions to the C language that are to be
recognised
-slashwhite
Whether to ignore whitespace between \ and the end of a
line
Identifiers
-namelength
Number of significant characters in internal identifiers
-xnamelength
Number of significant characters in an external identifiers
-xcase
Whether alphabetical case is significant in external identifier
System Headers
-si
Path to search for header files
-quiet
Suppress output to the database and .arc files for the
specified header file(s) and path
System Macros
-sd
Macros which are required by your compiler or development
environment
Implementation-Defined Types (option-intrinsictype)
In the header files associated with the standard ISO C library, type definitions exist for three characteristics of a C
compiler which are "implementation-defined". These are:
size_t
An unsigned integral type that reflects the type returned by the size of operator.
ptrdiff_t
A signed integral type that reflects the type resulting from the subtraction of two pointers.
wchar_t
An integral type whose range of values can accommodate all the extended (wide) characters
supported by the compiler.
The -intrinsictype option controls the way in which these types are implemented and needs to match your compiler
environment. Any corresponding typedef statements contained in header files (for example stddef.h, stdio.h)
must reflect how  Helix QAC for C is configured. In case of inconsistency,  Helix QAC for C will generate a Level 9 warning.
Examine your header files, if necessary, to determine appropriate settings for these options.
A set of standard library header files is shipped with  Helix QAC for C. If you make use of these stub headers, you need
not worry about intrinsic type settings. These headers contain typedef statements for ptrdiff_t, size_t and
wchar_t, which automatically reflect the intrinsic type settings. The typedef statements use three macro definitions,
PRQA_PTRDIFF_-T, PRQA_SIZE_T, and PRQA_WCHAR_T, which are implicitly defined within the  Helix QAC for C
environment and correspond to the default intrinsic type settings.
Page 17


---
*Page 17*

Compiler Extensions (option-extensions)
Many compiler manufacturers implement extensions to the ISO C language definition to take advantage of a particular
hardware environment. This is particularly true in embedded software environments where speed and "tight" code are
important.
The danger of using language extensions is that they compromise portability. Source code becomes dependent on the
compiler and hardware environment.
Helix QAC for C is able to parse a wide variety of language variations and extensions, but it is not usually able to interpret
the extensions semantically. Usually, the tool must be configured so that non-standard keywords are ignored.
The most common extensions to the C language can be handled with the -extensions option (refer to this option in the
Configuration Options appendix). These include the recognition of keywords such as near, far, and huge, the use of $ in
identifiers, and the handling of inline assembler blocks.
Extensions Classes
Helix QAC for C recognizes the following extension classes, which are also listed in the -extensions section of the
Configuration Options Appendix:
 n ansipc: Backslash (\) is permitted within filepaths. The keywords __near, __far, __huge, __cdecl, __
pascal, and __fortran are recognized and ignored. A warning message is issued.
 n PC: The keywords near, far, huge, cdecl, pascal, and fortran are recognized and ignored. A warning
message is issued.
 n asm: This option recognizes the assembler code directives #asm, #endasm and asm("string");. It enables a
number of inline assembler constructs to be parsed and ignored, that is to say:
 l The keywords asm and __asm used in the declaration of a function will cause that function to be ignored.
 l Assembler code blocks introduced by the keywords asm and __asm will be ignored.
 l Blocks of statements enclosed between the directives #asm and #endasm will be ignored.
 l In-line assembler statements of the form asm(...); will be ignored.
 l Functions referenced by a #pragma inline_asm will be ignored. Refer to Functions with Definitions in
Assembler.
Note:
If assembly language within #asm contains text that cannot be treated as raw C tokens, value errors will
still occur. However, this is only likely if single ’ or " characters appear.
 n C++: The reference operator & is recognized in declarations but has no semantic effect. C++ style comments are
allowed. Text between // and a new line is treated as a comment.
 n dollar: $ is legal in identifiers.
 n LONGLONG: Type "long long" is recognized as an extended data type. Properties of the type and conversion
rules will conform to the principles defined in the ISO C99 standard. If this option is not set, all references to type
"long long" result in generation of message 1027 and the type is treated as a synonym for type "long". The rules
that determine the type of a numeric integer are determined to conform to ISO C99. Unsuffixed decimal values
that are too large to fit in a "signed long" are of type "long long" rather than "unsigned long", if they fit.
 n VMS: $ is legal in identifiers. Filenames appearing in #include directives are mapped to lower case.
Page 18


---
*Page 18*

Functions with Definitions in Assembler
Many compilers support the feature of allowing a function to be defined with assembler statements directly. Support for
such compilers is enabled in  Helix QAC for C when extensions asm is set.  Helix QAC for C will then ignore the entire
function body of these functions. For example:
#pragma inline_asm func
void func(int x)
{
movw !_a, ax
}
will be parsed by  Helix QAC for C as if defined as follows:
#pragma inline_asm func
void func(int x)
{
}
Note:
Please note the following if you are using #pragma inline_asm:
 - The syntax is as follows: #pragma inline_asm [(]function-name [,...][)]
 - #pragma inline_asm must be specified prior to the definition of the function body.
Standard Extensions Defined via Macros (option -sd)
Helix QAC for C can be configured to handle extensions by defining macros, handling the ones specified with -d before
those specified with -systemdefine,-sd.
#define of extended keyword
Compiler manufacturers frequently introduce additional keywords such as idata, tiny, and  xhuge, to specify memory
models and allocate memory data. These keywords are often applied like storage class qualifiers in object declarations
and can be ignored during analysis by introducing a #define statement which defines away the keyword.
_ignore
The _ignore macro is an instruction to  Helix QAC for C to ignore not just a keyword but a sequence of tokens starting with
a specified keyword. It specifies a macro definition that handles the keyword in one of several ways.
using=_ignore
ignores using and the next token.
Page 19


---
*Page 19*

eseg=_ignore_semi
ignores eseg and everything up to and including the next semi-colon.
However, any code in parentheses is excluded from the search, which means
that any semi-colons within the parentheses are not taken into account.
asm=_ignore_paren
ignores asm and the contents of a block delimited by ( ), { } or [ ]
interrupt=_ignore_3
ignores interrupt and the following three tokens.
tiny=_ignore_at
ignores the @tiny sequence.
Locking the macro replacement list
It is illegal to redefine a macro to have a different replacement list without undefining the macro first (#undef). The default
behavior of Helix QAC for C  is to ignore the replacement list of the illegal redefinition.
#define A 1
#define A 2 /* Illegal redefinition - ignored */
int i = A;  /* Expands to 1 */
This behavior simplifies handling of extensions as identifiers can be given safe values at startup, and any subsequent
definitions by a compiler or 3rd party header will be ignored.
Some mainstream compilers, however, use the second replacement list rather than the first. The  -
rememberfirstdefinedirective,-remfdd option, when disabled, switches the behavior of Helix QAC for C  so that it uses the
second replacement list rather than the first.
/* Options: rememberfirstdefinedirective */
#define A 1
#define A 2 /* Illegal redefinition - replacement list updated */
int i = A; /* Expands to 1 */
Unfortunately, this means that a safe value given at startup will be replaced should a definition exist in the compiler or 3rd
party header set. This in turn may result in Helix QAC for C  being unable to parse the source. To address this, _ignore_
modification can be used to specify that the replacement lists of any macro redefinitions are to be ignored.
/* Options: rememberfirstdefinedirective */
#define A 1
#define A _ignore_modification
Page 20


---
*Page 20*

#define A 2 /* Illegal redefinition (but ignored) */
            int i = A; /* Expands to 1 */
To simplify the configuration process, by default Helix QAC for C  will treat macros defined in a -forceinclude,-fi header or
defined using the -systemdefine,-sd configuration option as implicitly also having _ignore_modification.
/* Options: rememberfirstdefinedirective- -fi f1.h */

/* f1.h */
#define A 1

/* f1.cc */
#define A 2 /* Redefinition of A (but ignored) */
int i = A; /* Expands to 1 */
This behavior can be further refined using the -prodoption ignore_modification::forceinclude and -prodoption ignore_
modification::systemdefine prodoptions.
Redefinition of Extended Data Types
Sometimes extended data types are introduced into the language to address memory-mapped I/O ports or to perform
efficient bit addressing. These data types can usually be redefined to a standard data type during analysis by introducing
a macro or a typedef.
For example, access to special function registers is often provided through data types such as sfr and sbit.
 #define sfr unsigned char
 typedef unsigned char sfr
Operators
The standard ISO C operators ^ and . are used in a non-standard way for bit selection in conjunction with the special
function register data types. If the data types have been introduced through a typedef or redefined as suggested above,
the ^ operator will be parsed successfully and interpreted as a "bitwise exclusive or" operator. The . operator, which is
normally the structure/union member selection operator, is also recognized by  Helix QAC for C when used as a bit
selection operator, but warning 3664 is generated. However, this warning can be suppressed if you wish to use the .
operator in this way.
System Header Files (option -si)
The ordering of the parameters is important.  Helix QAC for C will search the directories specified in the order in which
they are passed, processing the -i option before the -systeminclude,-si.
Page 21


---
*Page 21*

Suppress Output (option -quiet)
The  option can be used to specify that the output of a single file or all files in a path should be suppressed.
Note:
This option applies only to included files and has no effect on the main source file. Refer to the -quiet,-q
option in Configuration Options.
Suppressing analysis in this way will have the following impact:
 n Bodies of functions and function templates will not be parsed or analyzed in the files.1
 n .arc file will not be generated for the files.
 n Diagnostic output will not be written for the files.2
Additional Include Files (option -forceinclude)
If you want to define typedefs, they will need to be specified within your source code. However, rather than introducing
them directly into your source code or header files, usually it is better to create a special header file and "force-include"
this file during analysis. Refer to the  -forceinclude,-fi option in Configuration Options
The run-time absence of a specified force-include file will be flagged as a Level 9 error.
Type of Analysis
Option
Effect
General Processing
-encoding
The character set
-strictsignedness
This option is obsolete and has no effect
-strictrank
Behavior of implicit type conversion messages
-ppfilename
Show file names and line numbers in the preprocessed file
-maxerrors
Number of hard errors that will cause the analysis to stop
Dataflow Analysis
-enabledataflow
Whether the DF^2 dataflow analysis is performed
-po df::function_timeout
Limit the overall time spent in dataflow analysis for each function
-po df::struct_last_array_member_size_
1
Handle C99 language feature for flexible array member
1This can aid parsing of headers that contain extensions or non standard constructs not supported by  Helix QAC for C
2Diagnostics for QA_ERROR messages cannot be suppressed and so they will continue to be generated.
Page 22


---
*Page 22*

Option
Effect
Kernighan and Ritchie (K&R) Compatibility
-k+r
ISO language features that should be avoided if using a K&R
compiler
Metrics
-comment
Determines how the comment density metric (STCDN) is calculated
-ppmetrics
Include header file information in the calculation of metrics
-threshold
Output the specified message whenever the threshold for specified
metric is exceeded
Pragmas
-skippragma
Behavior of #pragma directives
Project Headers
-i
Path to search for header files
Project Macros
-d
Macros which are required by your compiler or development
environment
Style
-style
Enforce consistency with the specified bracing style
-indentlevel
Amount of space used to indent code
-maxlinelength
Enforce a maximum physical line length in the source code
-tabstop
Number of spaces represented by a tab character
Construct Warnings
-warncall
Generate the specified message if a call to the specified function is
encountered
-warnmacroexpansion
Generate the specified message if the specified macro is expanded in
the source code
-warnset
Generate the specified message if the specified member variable is set.
This also includes the optional ability to require a specific value
Page 23


---
*Page 23*

Project Header Files (option -i)
The ordering of the parameters is important.  Helix QAC for C will search the directories specified in the order they are
passed.
Dataflow Analysis Settings (options -po df::...)
Deep Flow Dataflow analysis (DF^2) is a sophisticated additional phase of analysis, see the Dataflow section for
information on its use and configuration.
Rules
Rules are used to categorize messages, and to select which message checks to apply. Rules are organized into a tree
structure. The rules at the bottom of the tree have messages mapped to them.
Rules are configured using the Rule Configuration tab of the Helix QAC Project Properties. The configuration settings
are read from, and written to, a Rule Configuration File with extension .rcf. The .rcf files can be copied between
projects to obtain consistent configurations. Please refer to the Helix QAC manual for more details on the management
of .rcf files and rules.
Rules have been designed as a flexible method to categorize messages in a way that is meaningful to a company and its
particular projects. It is possible to use different rules for different projects, or to use the same rules across many
projects. A default .rcf file is provided, which is described in Helix QAC for C.
By default all rules are enabled, but individual rules can easily be disabled. Disabling a rule means that all of its
descendants within the tree are also disabled. Only messages mapped to enabled rules are generated by  Helix QAC for
C. Disabling is sometimes used if a generic ruleset has been used but certain categories of message are not relevant for
the particular project. Disabling is also used on a more temporary basis, to detect and handle one category of message
at a time.
Page 24


---
*Page 24*
