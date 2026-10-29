# 3 | Configuration File

3 | Configuration File
This file, also referred to as the "name rules file", contains the rules to be used by Namecheck. As a minimum, each rule
should specify the pattern (Regular Expression) that is to be applied to each type of identifier (macros, functions,
typedefs, variables, etc).
You can have different rules for different types of identifier.
Rules are applied sequentially from the input configuration; no checking is done for contradictory rules, and more than
one rule can apply to a particular identifier.
For example, a company coding standard may have the following two rules:
1. Identifiers must be 31 characters or less in length.
2. Function names must begin with an upper case letter.
It is possible to have a function that violates either or both of these rules, so there may be cases where an identifier has
more than one message issued against it.
Rule Format (JSON Syntax)
The configuration file is based on the JSON syntax - see http://www.json.org/ for full details. The only difference is that
the configuration file uses single quotes to de-limit strings, rather than double quotes.
The JSON object is defined as a rule by beginning the line with ’rule=’. Blank lines and those starting with hash (#) are
ignored. Each rule must be on a separate line, and may not be split across two lines.
All the Rule Values are strings, except for the following:
n Invert is a Boolean (specified with the literal text true or false).
n Message Number is a positive number.
Note:
Note that an empty rule (rule={}) is allowed. This will issue message number 4800 against all identifiers.
Similarly the rule rule={’space’:’OV’} will issue message number 4800 against all variables. This can be
useful for checking that rules will apply to the intended identifiers before moving on to add the Regular
Expression.
Rule Names
Rules are constructed as follows:
<DEFINE> identifier filename lineno inc def space scope linkage type flag
For example:
Page 8


---
*Page 8*

<DEFINE> g file.c 6 N DC OV F X ni S
Note:
For the full lists of the values that the Rule Names can take, please refer to Define Record.
The Rule Names are described in the following sub-sections.
Filename
Name: filename
Value: string, regular expression
This object is used to specify particular files to which the rule applies. It is a Regular Expression. Only a file whose name
matches the regular expression has the rule applied to it.
Note:
The full path of the file is compared to the Regular Expression, so it is important to include the end-of-line
anchor ($) in the regular expression, to avoid matching fragments of the full path.
Included File
Name: inc
Value: string from 'inc' list
This specifies that the rule will only be applied to either the main source file or to those files included via the pre-
processor directive #include. When omitted, the rule will apply to both the main source and included files.
Definition
Name: def
Value: string from 'def' list
This restricts the rule to different forms of declaration/definition. When omitted, the rule will apply to all definitions and
declarations. Combinations of these values can be obtained by separating entries with commas or spaces.
Space
Name: space
Value: string from 'space' list
This restricts the rule to different types of identifier. When omitted, the rule will be applied to all identifiers. Combinations
of these values can be obtained by separating entries with commas or spaces.
Page 9


---
*Page 9*

Scope
Name: scope
Value: string from 'scope' list
This restricts the rule in terms of the scope of the identifier. When omitted, the rule will apply to identifiers with any scope.
Combinations of the values can be obtained by separating entries with commas or spaces.
Caution:
Scope and Linkage (below) are often confused.
Scope determines the visibility of a name, that is to say, when class constructors and destructors are
called, and when variables local to the scope are initialized.
Linkage determines whether identifiers that have identical names refer to the same entity, or even if
those identifiers appear in different source files.
Linkage
Name: linkage
Value: string from 'linkage' list
This restricts the rule in terms of the linkage of the identifier. When omitted, the rule will apply to identifiers with any
linkage.
Type
Name: type
Value: string, regular expression
This restricts the rule in terms of the type of an identifier. This is a Regular Expression utilizing a symbolic shorthand
notation. When omitted, the rule will apply to all types. Combinations of these values can be obtained by separating
entries with commas or spaces.
The type of an identifier is the actual type, rather than any typedef used. Take the following code:
typedef unsigned int UINT32;
UINT32 foo;
unsigned int bar;
Both ’foo’ and ’bar’ will have the type ’ui’ for unsigned int.
Page 10


---
*Page 10*

Flag
Name: flag
Value: string from 'flag' list
This restricts the rule in terms of additional information regarding the identifier. This is additional to the previous
information and helps narrow the identifier down. When omitted, the rule will apply to an identifier with any flag value,
including ’none’. The ’flag’ field in the define record may hold combinations of these values.
As an example, take the following code:
<DEFINE> ::foo<@ClassTempParam_1_0_>(@ClassTempParam_1_0_,@ClassTempParam_1_0_)
s.cc 4 N DC OF F X (@ClassTempParam_1_0_,@ClassTempParam_1_0_) U
The ’U’ at the end shows that, regardless of the other ’flags’ in the definition, the entity is an ’Uninstantiated template
or member of a template’.
Pattern
Name: pattern
Value: string, regular expression
This specifies the Regular Expression to match the identifier. When omitted, no identifiers will be matched - that is, they
fail the name check. This can be useful to verify that other parts of the rule are directed at the desired identifiers.
Invert
Name: invert
Value: Boolean
If specified as ’true’, this will invert the logic of the pattern matching. A Regular Expression can be constructed to
perform this negation; however, it may be easier (and easier to maintain) to specify what NOT to match. If omitted, the
results of the matches will not be inverted.
Message Number
Name: message
Value: number
This specifies the message number to issue if the identifier fails the pattern match. If this is omitted, the default message
(4800) will be generated.
Page 11


---
*Page 11*

Caution:
It is important that messages generated do not clash with other messages, whether from Primary
Analysis (1-4999) or any Secondary Analysis (5000+). If not using the default message (4800),
messages generated must be present in the user message file; otherwise, they will be displayed as Level
99 fatal errors.
Namespace
Name: namespace
Value: string, regular expression
This specifies the namespace within which the rule will be applied. The namespace for an identifier is the fully qualified
namespace. Identifiers within nested namespaces will have all the namespace names in their fully qualified name.
Define Record
<DEFINE> identifier filename lineno inc def space scope linkage type flag
Name rules can be written as if each identifier had the following record associated with it:
Define Records: Identifier
Field
Content
Description
identifier
Identifier name. The identifier name is qualified and could include scope, function
(with its symbolic type), and function block.
filename
File in which declaration appears
lineno
Line at which declaration appears
inc
I
Included file
N
Not included, i.e. main source file
def
DF
Definition
DC
Declaration
DR
Re-declaration
DI
Implicit defined function
DS
Specialization of a function or class
DX
Explicit specialization
Page 12


---
*Page 12*

Field
Content
Description
DP
Partial specialization
space
TG
Structure, union or enumeration tag
OT
Ordinary identifier - typedef
OF
Ordinary identifier - function
OE
Ordinary identifier - enumerator
OM
Ordinary identifier - macro
OV
Ordinary identifier - variable
scope
F
File
B
Block
C
Class
T
Template
S
Namespace
-
Not applicable (macros)
linkage
I
Internal
X
External
N
None - local or typedef
-
Not applicable (macros)
Type
Shorthand notation for types
Flag
F
Function-like
O
Object-like
I
Inline declaration
V
Virtual declaration
P
Pure virtual declaration
S
Static storage duration (local and global declarations. Not the same as static
keyword)
Page 13


---
*Page 13*

Field
Content
Description
L
Thread local duration
D
POD-class (C-style struct)
1,2,3
Explicitly public, protected, private access respectively
5,7
Implicitly public, private access respectively
R
Function parameter
U
Uninstantiated template or member of template
G
Getter/Accessor function
T
Setter/Mutator function
-
No further information
Table Define Records: Symbolic Type
Symbolic Type Code
Datatype
nc
signed char
uc
unsigned char
_c
char
wc, c16, c32
wchar_t, char16_t, char32_t
ns, ni, nl, nll
short, int, long, long long
us, ui, ul, ull
unsigned short, unsigned int, unsigned long, unsigned long long
_o
bool
fs, ff, fl
float, double, long double
.
void, as in ’void f(int)’ or ’int f(void)’
pX
pointer to an X
*TX
pointer to member of T, X T::*
*T(Y,A1,..,An)
pointer to member function of T, Y (T::*)(A1,..,An)
&X
reference to X, X&
&&X
rvalue reference to X, X&&
Page 14


---
*Page 14*

Symbolic Type Code
Datatype
(Y,A1,..,An)
function returning Y taking A1.. An
[N,X]
N-element array of X
sNAME
struct NAME
uNAME
union NAME
eNAME
enum NAME
lNAME
lambda closure type
nb
signed bit-field
ub
unsigned bit-field
np
nullptr_t
:
ellipsis, as in ’void f(int, ...)’
=X
const X
^X
volatile X
@ClassTempParam_
N_M_
Template parameter at depth N offset M
@ClassTempParam_
N_M_...
Variadic template parameter at depth N offset M
Example
Line
Number
Source Code
<DEFINE> entries
1
#define M(x) ((x) +
10)
<DEFINE> M file.c 1 N DF OM - - - F
2
int a = 0;
<DEFINE> a file.c 2 N DC OV F X ni S
<DEFINE> a file.c 2 N DF OV F X ni S
3
extern int b(char
*c);
<DEFINE> c file.c 3 N DC OV P N p_c R <DEFINE> b file.c 3 N DC OF F X
(ni,p_c) -
4
typedef double D;
<DEFINE> D file.c 4 N DC OT F N ff -
5
static int e(D f);
<DEFINE> f file.c 5 N DC OV P N ff R <DEFINE> e file.c 5 N DC OF F I (ni,ff) -
Page 15


---
*Page 15*

Line
Number
Source Code
<DEFINE> entries
6
extern int g;
<DEFINE> g file.c 6 N DC OV F X ni S
7
static float h (int i)
<DEFINE> i file.c 7 N DC OV B N ni R
<DEFINE> h file.c 7 N DC OF F I (fs,ni) -
<DEFINE> h file.c 7 N DF OF F I (fs,ni) -
8
{
9
int j;
<DEFINE> j file.c 9 N DC OV B N ni -
<DEFINE> j file.c 9 N DF OV B N ni -
10
struct k
<DEFINE> k file.c 10 N DC TG B N sk -
<DEFINE> k file.c 10 N DF TG B N sk -
11
{
12
int l;
<DEFINE> l file.c 12 N DC MB B N ni -
13
char m;
<DEFINE> m file.c 13 N DC MB B N _c -
14
} n;
<DEFINE> n file.c 14 N DC OV B N sk -
<DEFINE> n file.c 14 N DF OV B N sk -
15
j = i + g;
16
return(j);
17
}
Page 16


---
*Page 16*
