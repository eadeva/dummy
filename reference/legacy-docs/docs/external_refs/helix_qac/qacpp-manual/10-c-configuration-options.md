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
The alignment of data types may be constrained by your hardware and compiler. For example, your environment may
allocate a char at any memory address, but require an int to start on a four-byte boundary. Such constraints impose
restrictions on the validity of pointer conversions. For example, it might be valid to cast a pointer to int to a pointer to char
but, invalid to do the reverse. The analyzer generates warnings that identify dangerous pointer casts.
See the component manual for details on the product specific alignment options.
Page 135


---
*Page 135*

The available size and alignment values are constrained by the ISO rules on integral size ordering.
Helix QAC for C++ also uses data type alignment values to calculate the size of structures. Alignment is often related to
the size of a data type: see -size,-s.
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
The size and alignment of char16_t and char32_t are not configurable and will always use the size and alignment of uint_
least16_t and uint_least32_t respectively.
A new setting for C++17 is the "default_new" alignment value. This represents the standard __STDCPP_DEFAULT_
NEW_ALIGNMENT__ value. This is the alignment guaranteed by a call to operator new(std::size_t) or
operator new[](std::size_t). Larger alignments will call the new operator new(std::size_t,
std::align_val_t) etc.
"default_new" defaults to 16 bytes per most popular compilers. You should only need to change this default if your
compiler has a different value for __STDCPP_DEFAULT_NEW_ALIGNMENT__.
Page 136


---
*Page 136*

-allowconstconvdeduction,-accd
Syntax:
-allowconstconvdeduction[{+|-}]
Default:
-allowconstconvdeduction-
Category:
Advanced
Function:
When enabled, template argument deduction is allowed to succeed where deduced types differ by const
or volatile qualification.
According to the ISO Standard, template argument deduction for types should fail where the same template argument is
deduced to be different for two function arguments. This also applies where the types differ only by const or volatile.
For Example:
const int ci = 0;
int nci = 0;
template <typename T>
void foo (T &, T &);
void bar ()
{
// Succeeds with -allowconstconvdeduction+
foo (ci, nci);
}
-allowdpdtusingdecltype,-adudt
Syntax:
-allowdpdtusingdecltype[{+|-}]
Default:
-allowdpdtusingdecltype-
Category:
Advanced
Function:
When enabled, a dependent using declaration can introduce a type name, even if the typename
keyword is not used.
Page 137


---
*Page 137*

According to the ISO Standard, a name that is dependent on a template parameter is assumed not to name a type unless
the name is qualified by the 'typename' keyword. This also applies to member using declarations. When enabled, if the
name introduced in the class scope is used in an elaborated type specifier, it is assumed to refer to the base class entity
instead of declaring a new type.
For Example:
template<typename T>
struct A
{
struct C
{ };
};
template<typename T>
struct B : A<T>
{
using A<T>::C;
// return type refers to typename A<T>::C with -allowdpdtusingdecltype
struct C foo();
};
-allowfnptrconvdeduction,-afpcd
Syntax:
-allowfnptrconvdeduction[{+|-}]
Default:
-allowfnptrconvdeduction-
Category:
Advanced
Function:
When enabled, function-to-pointer conversions are allowed during template argument deduction.
Page 138


---
*Page 138*

This allows the analyzer to match template function partial ordering rules where a reference-to-function parameter is
considered more specialized than a pointer-to-function parameter.
For Example:
void f(int);
template <typename T1, typename>
void foo(T1 (& f) (T2));
template <typename T1, typename T2>
void foo(T1 (* f) (T2));
void bar()
{
// Not ambiguous with -allowfnptrconvdeduction+
foo(f);
}
-allowimplicitconvptrmbr,-aicpm
Syntax:
-allowimplicitconvptrmbr[{+|-}]
Default:
-allowimplicitconvptrmbr-
Category:
Advanced
Function:
When enabled, member functions are allowed to implicitly convert to pointer to member functions.
Page 139


---
*Page 139*

For Example:
struct A
{
int foo();
void bar()
{
// Succeeds with -allowimplicitconvptrmbr+
int (A::*pf)() = foo;
}
};
-allowimplicitlangconv,-ailc
Syntax:
-allowimplicitlangconv[{+|-}]
Default:
-allowimplicitlangconv+
Category:
Advanced
Function:
When enabled, language linkage is not considered part of a function.
Page 140


---
*Page 140*

Strict compliance to the standard would require that two function types with different linkage be modelled as distinct.
However, in practice, compilers do not distinguish between such types.
For Example:
extern "C" void bar(int);
template <typename T>
void f(const T &)
{ T::do_not_instantiate; }
template <typename R, typename T>
void f(R (&t)(T))
{ }
void foo()
{
// Calls f(R (&t)(T)) with -allowimplicitlangconv+
f(bar);
}
This option also changes the meaning of two function declarations, where parameters of the function have different
language linkage.
For Example:
extern "C" typedef void C_type ( void * );
typedef void CPP_type ( void * );
void f ( int ( * ) ( C_type ) ) {}
Page 141


---
*Page 141*

void f ( int ( * ) ( CPP_type ) ) {} // -ailc-: Overloads
// -alic+: Duplicate Definition
-allowrefcomparisonforuserdefconvseq,-arcfudcs
Syntax:
-allowrefcomparisonforuserdefconvseq[{+|-}]
Default:
-allowrefcomparisonforuserdefconvseq-
Category:
Advanced
Function:
When enabled user-defined conversion sequences are allowed to differ based on the reference type of
the parameters and the corresponding types of the argument expressions.
According to the ISO Standard, for two user-defined conversion sequences to be compared they must have the same
user-defined conversion function or initialize the same class in an aggregate initialization. However, some compilers
ignore the requirement for the same conversion function when the parameter is a reference type if a match can be
determined based on the second standard conversion sequence.
For Example:
struct A { int i; double j; };
struct B { int k; double l; };
void foo (A&&);
void foo (const B&);
void bar ()
{
// Succeeds with -allowrefcomparisonforuserdefconvseq+
foo({1,2});
}
Page 142


---
*Page 142*

-allowtempnonconstrefbind,-atncrb
Syntax:
-allowtempnonconstrefbind[{+|-}]
Default:
-allowtempnonconstrefbind-
Category:
Advanced
Function:
When enabled, temporaries are allowed to be bound to non-const references.
According to the ISO Standard, a temporary can only be bound to a const reference, however some compilers do not
enforce this constraint.
For Example:
struct A
{
};
void foo ()
{
// Succeeds with -allowtempnonconstrefbind+
  A & a = A();
}
-allowtmplargnullptrconv,-atanpc
Syntax:
-allowtmplargnullptrconv[{+|-}]
Default:
-allowtmplargnullptrconv-
Category:
Advanced
Function:
When enabled, null pointer conversions are allowed for non-type template arguments.
Page 143


---
*Page 143*

For Example:
template <int *>
struct A
{
};
void foo ()
{
// Succeeds with -allowtmplargnullptrconv+
  A<0> a;
}
-alwaysusedirectinitializer,-audi
Syntax:
-alwaysusedirectinitializer[{+|-}]
Default:
-alwaysusedirectinitializer-
Category:
Advanced
Function:
When enabled, direct rather than copy initialization is used for declarations of the form 'T x = e'.
Page 144


---
*Page 144*

For Example:
struct B;
struct A
{
A(B&);
};
struct B
{
operator A();
};
void foo (B & b)
{
// Not ambiguous with -alwaysusedirectinitializer+
  A a = b;
}
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
Page 145


---
*Page 145*

The ISO Standard states that the result of an arithmetic right shift on a negative signed number is implementation-
defined. That is, each individual compiler has to specify the effect of shifting negative values right.
This option is included in the analyzer to support the general bit-field treatment of data types in the common dataflow
module.
-prodoption assert::no_override
Syntax:
-prodoption assert::no_override[{+|-}]
Default:
-prodoption assert::no_override-
Category:
Basic
Function:
Don't override the definition of the 'assert' macro
To perform analysis for message 3912 the parser replaces the 'assert' macro with its own definition (even if 'NDEBUG'
has been defined). This can affect dataflow analysis as it will always take 'assert' expressions into account, for example:
#define NDEBUG 1
#include <cassert>
char array[10];
char foo(unsigned int i)
{
assert(i < 10);
return array[i]; // message 2844 only generated
// with -po assert::no_override
}
See Modeling of the assert macro for more information.
-prodoption basic_character_set::ignore
Syntax:
-prodoption basic_character_set::ignore=characters
Page 146


---
*Page 146*

Default:
no entry
Category:
Basic
Function:
Specifies a list of common characters that should be treated as members of the basic character set.
If a character is specified to the -po basic_character_set::ignore option, then it will be considered as a member
of the basic character set and so will not generate messages relating to use outside of this character set.
See also:
n -po basicchar::set
n -po basic_character_set::ignore
n -po basic_character_set_string_literal::ignore
n -po basic_character_set_comment::ignore
Note:
Values used by configuration options may also be specified through environment variables:
-d var=$env
As a result, to specify a '$' character in the basic character set it needs to be switched with '\':
-prodoption basicchar::set='\$'
-prodoption basic_character_set_comment::ignore
Syntax:
-prodoption basic_character_set_comment::ignore=characters
Default:
no entry
Category:
Basic
Function:
Specifies a list of common characters that should be treated as members of the basic character set in
comment.
Page 147


---
*Page 147*

If a character is specified to the -po basic_character_set_comment::ignore option, then it will be considered
as a member of the basic character set when used in a comment and so will not generate messages relating to use
outside of this character set.
See also:
n -po basicchar::set
n -po basic_character_set::ignore
n -po basic_character_set_string_literal::ignore
Note:
Values used by configuration options may also be specified through environment variables:
-d var=$env
As a result, to specify a '$' character in the basic character set it needs to be switched with '\':
-prodoption basicchar::set='\$'
-prodoption basic_character_set_string_literal::ignore
Syntax:
-prodoption basic_character_set_string_literal::ignore=characters
Default:
no entry
Category:
Basic
Function:
Specifies a list of common characters that should be treated as members of the basic character set in
string literal.
If a character is specified to the -po basic_character_set_string_literal::ignore option, then it will be
considered as a member of the basic character set when used in a string literal and so will not generate messages to use
outside of this character set.
See also:
n -po basicchar::set
n -po basic_character_set::ignore
n -po basic_character_set_comment::ignore
Note:
Values used by configuration options may also be specified through environment variables:
-d var=$env
As a result, to specify a '$' character in the basic character set it needs to be switched with '\':
-prodoption basicchar::set='\$'
Page 148


---
*Page 148*

-prodoption basicchar::set
Syntax:
-prodoption basicchar::set=characters
Default:
-prodoption basicchar::set=`\\$@
Category:
Basic
Function:
Specifies a list of characters that are not in the basic character set but are common and are known to be
supported in the target environment.
Characters not in the basic character set and not specified to this option will generate one of the following messages:
If not in the basic character set and not specified to -po basicchar::set:
1095 The character 'char' is not in the basic character set.
If not in the basic character set and specified to the -po basicchar::set:
1096 The character 'char' is common, but not in the basic character set.
Note:
Values used by configuration options may also be specified through environment variables:
-d var=$env
As a result, to specify a '$' character in the basic character set it needs to be switched with '\':
-prodoption basicchar::set='\$'
-bitsigned,-bits
Syntax:
-bitsigned[{+|-}]
Default:
-bitsigned+
Category:
Advanced
Function:
Defines whether plain integer bit-fields are treated as signed int (-bitsigned+) or unsigned int (-
bitsigned-).
Page 149


---
*Page 149*

The ISO Standard states that the sign of a bit-field that is not explicitly signed or unsigned is implementation-defined.
For Example:
struct
{
signed int sbit : 3;
/* holds values between -4 and +3       */
unsigned int ubit : 5; /* holds values between 0 and 31        */
int bit : 4;
/* may hold values between -8 and +7 or
                            between 0 and 15                     */
} x;
-prodoption class_usage::max_header_depth
Syntax:
-prodoption class_usage::max_header_depth=limit
Default:
-prodoption class_usage::max_header_depth=2
Category:
Basic
Function:
Controls how deep in the include tree to search for type definitions to analyze.
Further explanation can be found in the help for message 1062.
-coderegex,-cre
Syntax:
-coderegex s/regex/replacement/modifiers
Default:
no entry
Category:
Basic
Function:
When specified, this option can be used to replace sections of code that match a regular expression.
Page 150


---
*Page 150*

Note:
Characters such as single or double quotes, brackets and '.' have special meaning in regular
expressions. Depending on the intended meaning of such characters, standard switching of these
characters may be required.
When specified, this option can be used to replace sections of code that match the regular expression. This may be
particularly useful for:
n Working around unsupported compiler extensions,
n Automatically controlling message visibility for auto generated code,
n Applying custom non-intrusive suppressions.
Optional Modifiers:
The following modifiers are supported:
n [l] Do not pad replacement expression with newlines
n [c] Do not pad replacement expression with spaces
Code replacement is particularly useful for handling non-standard language extensions. For example, the __property
extension can be supported using the following:

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
See 'Advanced Topics' in the user manual for more information (Code Replacement).
-prodoption comment::dynamic_statistics
Syntax:
-prodoption comment::dynamic_statistics[{+|-}]
Page 151


---
*Page 151*

Default:
-prodoption comment::dynamic_statistics+
Category:
Basic
Function:
This option allows you to control the update behavior of the analysis of commented out code. When the
option is enabled (which it is by default), source token statistics continue to be gathered from the TU
(Translation Unit) under analysis, to improve commented out code detection.
In order to generate the analysis of commented out code, an algorithm is used to compare comments against a table of
"common code sequences" gathered from real-world, standard-compliant projects. As long as the "comment::dynamic_
statistics" option is enabled, triplets are gathered from uncommented sections of the TU being analyzed, so that unusual
constructions or non-standard language extensions that appear elsewhere in the TU can be matched.
For example:
int f (int x, int y) {
return ({ int w = x + y; w; });
// Statement expressions are a non-standard
extension
}
// This will be recognized as commented out code if, and only if, we
// gather statistics from the current TU
/* return ({ int j = a; j; }); */
// Message only if -po comment::dynamic_statistics+
The option is enabled by default, so that comments can be matched more accurately against the actual code in use, but
this does mean that changes in one part of a TU may have unexpected effects on message generation in an apparently
unrelated part of the TU. Disabling the option will ensure that commented out code detection is determined entirely
locally, so that the same table of "common code sequences" is used throughout.
-prodoption conv::allow_bitfield_bool_conv
Syntax:
-prodoption conv::allow_bitfield_bool_conv[{+|-}]
Default:
-prodoption conv::allow_bitfield_bool_conv-
Category:
Basic
Function:
Controls bitfield conversion to bool.
Page 152


---
*Page 152*

When enabled, contextual conversion to bool is allowed for expressions whose type is an integral bitfield of size 1.
-prodoption conv::allow_cntx_bool_conv
Syntax:
-prodoption conv::allow_cntx_bool_conv[{+|-}]
Default:
-prodoption conv::allow_cntx_bool_conv-
Category:
Basic
Function:
Controls contextual conversion to bool.
When enabled, contextual conversion to bool is allowed for expressions whose type is:
n a pointer type
n a class type having an explicit operator bool()
-c++03alignment,-c++03align
Syntax:
-c++03alignment[{+|-}]
Default:
-c++03alignment-
Category:
Advanced
Function:
When enabled, alignas or alignof are not treated as keywords.
For Example:
void foo()
{
// Succeeds with -c++03alignment+
int alignas;
int alignof;
}
-c++03auto,-c++03a
Syntax:
-c++03auto[{+|-}]
Page 153


---
*Page 153*

Default:
-c++03auto-
Category:
Advanced
Function:
When enabled, the 2003 ISO Standard rules will be used for the auto keyword.
The 2011 ISO Standard changed auto from being a storage-class-specifier to a type-specifier, this option controls which
behavior is used.
For Example:
void foo()
{
// Succeeds with -c++03auto+
auto int i;
}
-c++03constexpr,-c++03ce
Syntax:
-c++03constexpr[{+|-}]
Default:
-c++03constexpr-
Category:
Advanced
Function:
When enabled, support for the constexpr language feature is removed, and the number of expressions
considered to be valid 'constant integral expressions' is reduced accordingly. Finally, constexpr is no
longer treated as a keyword.
Page 154


---
*Page 154*

For Example:
void foo()
{
// Succeeds with -c++03constexpr+
int constexpr;
}
template<int I>
struct A
{ };
A<(1, 2)> a; // fails with -c++03constexpr+
-c++03decltype,-c++03dt
Syntax:
-c++03decltype[{+|-}]
Default:
-c++03decltype-
Category:
Advanced
Function:
When enabled, decltype is not treated as a keyword.
Page 155


---
*Page 155*

For Example:
void foo()
{
// Succeeds with -c++03decltype+
int decltype;
}
-c++03exceptionspecification,-c++03es
Syntax:
-c++03exceptionspecification[{+|-}]
Default:
-c++03exceptionspecification-
Category:
Advanced
Function:
When enabled, the 2003 ISO Standard rules will be used for exception specifications on implicit member
functions and operator new.
Page 156


---
*Page 156*

For Example:
struct A { ~A(); };
struct B : public A {
// ~B() noexcept; with -c++03exceptionspecification-
// ~B();          with -c++03exceptionspecification+
};
void f (B * b) throw (int)
{
//
// With -c++03exceptionspecification+
//   4632 Function without an exception specification called
//        from a function with an exception specification.
//
// With -c++03exceptionspecification-
//   4039 The following type is not thrown by the function: 'int'.
//
  b->~B();
}
-c++03initializer,-c++03init
Syntax:
-c++03initializer[{+|-}]
Default:
-c++03initializer-
Category:
Advanced
Function:
When enabled, the 2003 ISO Standard rules will be used for aggregate initialization.
Page 157


---
*Page 157*

For Example:
struct A
{
int i;
operator int () const; // only called with c++03init
};
struct B
{
  A a;
};
void foo(A a)
{
  B b = { { a } };
}
-c++03linkage,-c++03l
Syntax:
-c++03linkage[{+|-}]
Default:
-c++03linkage-
Category:
Advanced
Function:
When enabled, members of unnamed namespaces will not have implicit internal linkage.
Page 158


---
*Page 158*

For Example:
namespace {
// With -c++03linkage+ 'foo' given external linkage
// With -c++03linkage- 'foo' given internal linkage
void foo ();
}
-c++03nomove,-c++03nm
Syntax:
-c++03nomove[{+|-}]
Default:
-c++03nomove-
Category:
Advanced
Function:
When enabled, implicit move constructors or assignment operators will not be declared.
Page 159


---
*Page 159*

For Example:
struct A {
//
// Implicit declarations for:
//   A();
//   ~A() noexcept;
//   A(A const &);
//   A& operator=(A const &);
//
// With -c++03nomove- also declares:
//   A(A&&);
//   A& operator=(A&&);
//
};
-c++03nostaticassert,-c++03nsa
Syntax:
-c++03nostaticassert[{+|-}]
Default:
-c++03nostaticassert-
Category:
Advanced
Function:
When enabled, static_assert is not treated as a keyword.
Page 160


---
*Page 160*

For Example:
void foo()
{
// Succeeds with -c++03nostaticassert+
int static_assert;
}
-c++03nounicodechartypes,-c++03nuct
Syntax:
-c++03nounicodechartypes[{+|-}]
Default:
-c++03nounicodechartypes-
Category:
Advanced
Function:
When enabled, char16_t and char32_t are not treated as keywords.
For Example:
void foo()
{
// Succeeds with -c++03nounicodechartypes+
int char16_t;
int char32_t;
}
-c++03nouserdefinedliterals,-c++03nudl
Syntax:
-c++03nouserdefinedliterals[{+|-}]
Page 161


---
*Page 161*

Default:
-c++03nouserdefinedliterals-
Category:
Advanced
Function:
When enabled, a string literal and adjacent suffix will not be parsed as a user defined literal.
For Example:
void foo()
{
// Succeeds with -c++03nouserdefinedliterals+
"Hello"__FILE__;
}
-c++03nullptr,-c++03np
Syntax:
-c++03nullptr[{+|-}]
Default:
-c++03nullptr-
Category:
Advanced
Function:
When enabled, nullptr is not treated as a keyword.
For Example:
void foo()
{
// Succeeds with -c++03nullptr+
int nullptr;
}
Page 162


---
*Page 162*

-c++03nullptrconst,-c++03npc
Syntax:
-c++03nullptrconst[{+|-}]
Default:
-c++03nullptrconst-
Category:
Advanced
Function:
When enabled, any integral constant expression evaluating to '0' is treated as a null pointer constant.
For Example:
void foo()
{
// Succeeds with -c++03nullptrconst+
int *ptr = (1 - 1);
}
-c++03plainolddata,-c++03pod
Syntax:
-c++03plainolddata[{+|-}]
Default:
-c++03plainolddata-
Category:
Advanced
Function:
When enabled, the 2003 ISO Standard rules for POD (plain old data) types are used.
Page 163


---
*Page 163*

For Example:
struct A // POD in C++11, but not in C++03
{
int getValue () const;
private:
int m_value;
};
-c++03threadlocal,-c++03tl
Syntax:
-c++03threadlocal[{+|-}]
Default:
-c++03threadlocal-
Category:
Advanced
Function:
When enabled, thread_local is not treated as a keyword.
For Example:
void foo()
{
// Succeeds with -c++03threadlocal+
int thread_local;
}
Page 164


---
*Page 164*

-c++11autodeduction,-c++11auto
Syntax:
-c++11autodeduction[{+|-}]
Default:
-c++11autodeduction-
Category:
Advanced
Function:
When enabled, the 2011 ISO Standard rules for auto type deductions are used.
For Example:
void foo()
{
// deduced as std::initializer_list<int> with -c++11autodeduction+
auto l = { 1 };
}
-c++11nodigitseparators,-c++11nds
Syntax:
-c++11nodigitseparators[{+|-}]
Default:
-c++11nodigitseparators-
Category:
Advanced
Function:
When enabled, use of a single quote character as a digit separator is not allowed.
Page 165


---
*Page 165*

For Example:
#define M(x, ...) __VA_ARGS__
void foo()
{
int x[] = { 0, M(1'2,3'4) }; // single element array with
// -c++11nodigitseparators
}
-c++11nosizeddeallocation,-c++11nsd
Syntax:
-c++11nosizeddeallocation[{+|-}]
Default:
-c++11nosizeddeallocation-
Category:
Advanced
Function:
When enabled, sized deallocation functions will not be implicitly defined in the global scope.
Page 166


---
*Page 166*

For Example:
struct A
{ }
void operator delete (void *ptr)
{ }
void foo(A *a)
{
delete a; // will call unsized deallocation function with
// -c++11nosizeddeallocation+
}
-c++14aggregate,-c++14agg
Syntax:
-c++14aggregate[{+|-}]
Default:
-c++14aggregate-
Category:
Advanced
Function:
When enabled, a class with a base class will never be an aggregate.
Page 167


---
*Page 167*

The 2017 ISO Standard allows aggregates to have public, non-virtual base classes.
For Example:
struct B
{
int b;
};
struct D : B
{
int i;
};
struct A
{
A(B, int);
};
void foo(D);
void foo(A);
void bar()
{
foo({ { 1 }, 2 }); // calls 'foo(A)' with -c++14aggregate, ambiguous otherwise
}
Page 168


---
*Page 168*

-c++14constexpr,-c++14ce
Syntax:
-c++14constexpr[{+|-}]
Default:
-c++14constexpr-
Category:
Advanced
Function:
When enabled, lambda expressions are never implicitly declared 'constexpr' and not all constant
expressions can be used as non-type template arguments of non-integral type.
Page 169


---
*Page 169*

The 2017 ISO Standard implicitly declares any lambda expression 'constexpr' if it doesn't violate any of the rules for
'constexpr' functions.
The 2017 ISO Standard also allows any converted constant expression to be used as a non-type template argument.
For Example:
template<int I>
struct A
{ };
void foo()
{
const int i = [] () { return 1; } ();
  A<i> a; // fails with -c++14constexpr+
}
template<int &I>
struct C
{ };
int i;
int j;
constexpr int &getNta(bool b)
{
return b ? i : j;
}
Page 170


---
*Page 170*

void bar()
{
  C<getNta(true)> c; // fails with c++14constexpr+
}
-c++14exceptionspecification,-c++14es
Syntax:
-c++14exceptionspecification[{+|-}]
Default:
-c++14exceptionspecification-
Category:
Advanced
Function:
When enabled, exception specifications are not part of the function type.
The 2017 ISO Standard made the exception specification part of the function type.
For Example:
#include <type_traits>
void f();
void g() noexcept;
static_assert(! std::is_same<decltype(f), decltype(g)>(),
"types are different in C++'17");
-c++14noextendedoperatornew,-c++14neon
Syntax:
-c++14noextendedoperatornew[{+|-}]
Default:
-c++14noextendedoperatornew-
Page 171


---
*Page 171*

Category:
Advanced
Function:
When enabled, C++17 support for non-standard alignment of objects is not available.
The 2017 ISO Standard added support for non-standard alignment of objects with new-extended overloads of the 'new'
operator.
For Example:
class alignas(32) Pos3d {
double x, y, z;
};
Pos3d* p = new Pos3d(); // doesn't call new-extended overload if -c++14neon+
-c++14noguaranteedcopyelision,-c++14ngce
Syntax:
-c++14noguaranteedcopyelision[{+|-}]
Default:
-c++14noguaranteedcopyelision-
Category:
Advanced
Function:
When enabled, a temporary object will be created for prvalues, which may require a call to the copy or
move constructors.
Page 172


---
*Page 172*

For Example:
struct A
{
A();
explicit A (A const &) = delete;
explicit A (A &&) = delete;
};
void f1(A);
void f2()
{
f1 ( A{} );
// Fails with -c++14noguaranteedcopyelision+
}
A f3()
{
return A{};
// Fails with -c++14noguaranteedcopyelision+
}
-c++14notypefromntadeduction,-c++14ntfnd
Syntax:
-c++14notypefromntadeduction[{+|-}]
Default:
-c++14notypefromntadeduction-
Category:
Advanced
Function:
When enabled, a template type parameter cannot be deduced from the type of non-type template
argument.
Page 173


---
*Page 173*

For Example:
template<int I>
struct C
{ };
template<typename T, T n>
void foo(C<n> const & c, int i) = delete;
template<int n>
void foo(C<n> const & c, short s);
void bar(C<1> const & c)
{
// Succeeds with -c++14notypefromntadeduction
foo(c, 1);
}
-c++14noutf8charliteral,-c++14nucl
Syntax:
-c++14noutf8charliteral[{+|-}]
Default:
-c++14noutf8charliteral-
Category:
Advanced
Function:
When enabled, u8 is not recognizes as a character literal prefix.
Page 174


---
*Page 174*

For Example:
#define u8 + (int)
void foo()
{
// Succeeds with -c++14noutf8charliteral+
int c = 1 u8' ';
}
-c++14sequenceorder,-c++14so
Syntax:
-c++14sequenceorder[{+|-}]
Default:
-c++14sequenceorder-
Category:
Advanced
Function:
When enabled, the order of evaluation of any part of any expression follows the C++ '14 rules.
The 2017 ISO Standard introduced new evaluation order guarantees to make execution safer and more intuitive to
programmers.
-c++14trigraphs,-c++14tg
Syntax:
-c++14trigraphs[{+|-}]
Default:
-c++14trigraphs-
Category:
Advanced
Function:
When enabled, trigraph sequences will be replaced.
Page 175


---
*Page 175*

The 2017 ISO Standard removed support for trigraph sequences. With this option, sequences beginning with "??"
(trigraphs) will be replaced with a single character. This affects comments and string literals.
For Example:
static_assert(sizeof("??(??)") == 7
, "this will fail if trigraphs are replaced");
-c++17nochar8type,-c++17nc8t
Syntax:
-c++17nochar8type[{+|-}]
Default:
-c++17nochar8type-
Category:
Advanced
Function:
When enabled, char8_t is not treated as a keyword and the type of a 'u8' literal is a narrow char.
For Example:
void foo()
{
// Succeeds with -c++17nochar8type+
int char8_t;
// Type of 'c' will be 'char'
auto c = u8'c';
}
Note:
Enabling either of -c++03nounicodechartypes,-c++03nuct or -c++14noutf8charliteral,-c++14nucl will
also disable this feature.
Page 176


---
*Page 176*

-c++17noconcepts,-c++17nc
Syntax:
-c++17noconcepts[{+|-}]
Default:
-c++17noconcepts-
Category:
Advanced
Function:
When enabled, neither 'concept' nor 'requires' will be parsed as keywords.
The 2020 ISO Standard added concepts. This feature improves error handling and provides a more intuitive approach to
template meta-programming.
The identifiers 'concept' and 'requires' are keywords in C++ '20, and so code written for versions of C++ before C++ '20
may fail to compile.
-c++17noexplicitbool,-c++17neb
Syntax:
-c++17noexplicitbool[{+|-}]
Default:
-c++17noexplicitbool-
Category:
Advanced
Function:
When enabled, '(' following 'explicit' will not be parsed as part of the explicit specifier.
The 2020 ISO Standard enhances explicit function specifier to accept an optional (constant expression).
C++ '20 specifies that a ( token, which follows explicit is parsed as part of the explicit specifier. This may cause code
valid in C++ '17 to not parse successfully in C++ '20. This option removes parsing support for explict(bool) meaning
the tool will parse such tokens in strict C++ '17 mode.
For Example:
struct A
{
explicit (A) ();
// Requires -c++17neb in order to parse as equivalent to:
// explicit A ();
};
Page 177


---
*Page 177*

-c++17nothreewaycomparison,-c++17ntwc
Syntax:
-c++17nothreewaycomparison[{+|-}]
Default:
-c++17nothreewaycomparison-
Category:
Advanced
Function:
When enabled, '<=>' will be treated as a '<=' token followed by a '>' token.
The 2020 ISO Standard added the three-way comparison operator. Based on the value of the operands to this operator,
it will return a value less than zero, equal to zero, or greater than zero.
There are some edge case situations where code legal in C++ '17 does not parse in C++ '20 due to the addition of the
<=> token. This option removes parsing support <=> meaning the tool will parse such tokens in strict C++ '17 mode.
For Example:
struct A
{
bool operator<= (A const &);
};
template <bool (A::*pf)(A const &)>
struct B
{
};
void foo ()
{
  B<&A::operator<=> a;
// Requires -c++17ntwc in order to parse as:
// B< &A::operator<= >
}
Page 178


---
*Page 178*

-d
Syntax:
-d ident[=[value]]
Default:
no entry
Category:
Basic
Function:
Defines macros for use in parsing.
The compilation of source code is often controlled by macros supplied to the compiler through command line options.
Macros can be supplied on command line using -d. Command line macros can also be undefined using the -undef
option.
Macros may also be specified using the -systemdefine option.
There are three ways to define a macro:
#define ident 1        /* Command line equivalent: -d ident       */
#define ident value    /* Command line equivalent: -d ident=value */
#define ident          /* Command line equivalent: -d ident=      */
Page 179


---
*Page 179*

Source code often includes constructs that are not part of the ISO Standard. Compiler vendors frequently introduce new
keywords in order to extend the language. To be able to parse these extensions, Helix QAC for C++ provides some
special macros that can be used to help with supporting 3rd party libraries.
-d ident=_
ignore
ignores the specified identifier and the next token.
-d ident=_
ignore_semi
ignores the identifier and everything up to and including the next semi-colon (;). However, any code
in parentheses is excluded from the search, which means that any semi-colons within the
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
fixes the current replacement list (if any) for ident. All subsequent uses of ident with #define
directives will be ignored. See -rememberfirstdefinedirective,-remfdd. This option does not apply to
#undef. To avoid the undefinition of a macro, a -coderegex,-cre can be used to remove the directive
completely.
The ignore operation is processed before any other macro substitution takes place.
This option is cumulative, see -forgetall,-forget,-f.
Note:
The value and semantics of macros specified using -systemdefine,-sd are identical to those using -d,
however macros specified with -d are processed before those specified with -systemdefine.
Note:
_munch. The macro _munch is a deprecated alternative to _ignore.
-delayparsefntemplates,-dpft
Syntax:
-delayparsefntemplates[{+|-}]
Default:
-delayparsefntemplates-
Category:
Advanced
Function:
When enabled, parsing of function templates are delayed until they are being instantiated.
Page 180


---
*Page 180*

This behavior is required when analyzing MFC or ATL source.
For example:
template <typename T>
void foo ()
{
// Succeeds with -delayparsefntemplates+
++NS::i;
}
namespace NS
{
int i;
}
void bar ()
{
  foo<int> ();
}
-prodoption df::analyse_header_functions
Syntax:
-prodoption df::analyse_header_functions=[{inter|intra}]
Default:
-prodoption df::analyse_header_functions=inter
Category:
Advanced
Function:
This option controls how functions defined in header files are analyzed.
When enabled, analysis of functions defined in header files will take place. This can result in duplicate analysis of
functions in each translation unit including the header file.
See the Dataflow manual for more information.
Page 181


---
*Page 181*

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
This may curtail related results, and is designed to avoid lengthy analysis attempts on severely complex functions.
This option only applies when dataflow is enabled (-enabledataflow+).
This option can be specified both for the Helix QAC for C and/or Helix QAC for C++ components as well as the Dataflow
component. See the Dataflow manual for more information.
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
When enabled, analysis will use the real size of single element array members declared at the end of a structure
definition.
-prodoption df::variant_unions
Syntax:
-prodoption df::variant_unions[{+|-}]
Default:
-prodoption df::variant_unions-
Category:
Advanced
Function:
Specifies that unions are used as variant types.
Unions with a large size can be very costly for the SMT solver. A union that is not used to reinterpret the bits, but as a
variant type, can be handled as a struct without loss of any analysis precision thus improving performance.
Type punning through unions is undefined behaviour when this option is enabled.
Page 182


---
*Page 182*

-prodoption digit_separator::binary_group
Syntax:
-prodoption digit_separator::binary_group=limit
Default:
no entry
Category:
Basic
Function:
Sets the expected length for group of digits in binary literals
If integer literal has any group of digits which is different length of the specified by this parameters, then message 4420
will be generated:
4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::binary_group=4" to analyze the following code will raise a
message 4420:
const int dl1 = 0b1'0101'1111 ;
const int dl2 = 0b0'10111;                 // expect:4420
-prodoption digit_separator::decimal_group
Syntax:
-prodoption digit_separator::decimal_group=limit
Default:
no entry
Category:
Basic
Function:
Sets the expected length for group of digits in decimal literals
Page 183


---
*Page 183*

If integer literal has any group of digits which is different length of the specified by this parameters, then message 4420
will be generated:
4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::decimal_group=3" to analyze the following code will raise a
message 4420:
const int dl1 = 1'000'000;
const int dl2 = 1'00'000;
// expect:4420
long unsigned int ui5 = 1'123'123ul;
long unsigned int ui6 = 1'123123ul;     // expect:4420
-prodoption digit_separator::floating_group
Syntax:
-prodoption digit_separator::floating_group=limit
Default:
no entry
Category:
Basic
Function:
Sets the expected length for group of digits in floating part of float literals
Page 184


---
*Page 184*

The floating part belongs the digits before the dot character. For instance:
n If literal is "1234.32e-10" then the floating part is "1234".
n If literal is "-12.10F" then the floating part is "12".
If floating part has any group of digits which is different length of the specified by this parameters, then message 4420 will
be generated:
4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::floating_group=3" to analyze the following code will raise a
message 4420:
const float dl1 = 1'000'000.5007;
const double dl2 = 100'0.50;                 // expect:4420
-prodoption digit_separator::fractional_group
Syntax:
-prodoption digit_separator::fractional_group=limit
Default:
no entry
Category:
Basic
Function:
Sets the expected length for group of digits in fractional part of float literals
Page 185


---
*Page 185*

The fractional part belongs the digits between the dot character and the exponent (if it exists). For instance:
n If literal is "1234.32e-10" then the fractional part is "32".
n If literal is "-12.10F" then the fractional part is "10".
If fractional part has any group of digits which is different length of the specified by this parameters, then message 4420
will be generated:
4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::fractional_group=3" to analyze the following code will raise a
message 4420:
const float dl1 = 1000000.500'7;
const double dl2 = 1000.5'007;                 // expect:4420
const float dl3 = 1.500'7e-12F;
const double dl4 = 1000.5'007e10L;             // expect:4420
-prodoption digit_separator::hex_group
Syntax:
-prodoption digit_separator::hex_group=limit
Default:
no entry
Category:
Basic
Function:
Sets the expected length for group of digits in hexadecimal literals
Page 186


---
*Page 186*

If integer literal has any group of digits which is different length of the specified by this parameters, then message 4420
will be generated:
4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::hex_group=4" to analyze the following code will raise a message
4420:
const int dl1 = 0xAB'F16C;
const int dl2 = 0xA'BF16C;                 // expect:4420
-prodoption digit_separator::non_separated_max_size
Syntax:
-prodoption digit_separator::non_separated_max_size=limit
Default:
-prodoption digit_separator::non_separated_max_size=10
Category:
Basic
Function:
Maximum size of numeric literals which don't use separators.
Page 187


---
*Page 187*

Specifies the maximum size for numeric literals that don't use separators. For floating point literals, the max size is
applied on both the whole and fractional parts individually.
For example, using -po digit_separator::non_separated_max_size=5:
void foo()
{
100'000'000;
// OK, has separator
12345;
// OK, not over 5 digits
1000000;
// expect:4421 Over 5 digits without separator
0xabcd'1234;  // OK, has separator
0xd1234;
// OK, not over 5 digits
0x654321;
// expect:4421 Over 5 digits without separator
1.123'456;    // OK, whole part not over 5 digits and fractional has separator
12'456.12345; // OK, whole part has separator and fractional not over 5 digits
1.234567;
// expect:4421 Fractional part is over 5 digits without separator
123456.7;
// expect:4421 Whole part is over 5 digits without separator
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
Page 188


---
*Page 188*

If integer literal has any group of digits which is different length of the specified by this parameters, then message 4420
will be generated:
4420 Digits in this literal are not separated to form groups of ${group_size}
digits.
For example, using -po "digit_separator::octal_group=4" to analyze the following code will raise a message
4420:
const int dl1 = 07'4545;
const int dl2 = 074'545;                   // expect:4420
-dontusec99decintlittypes,-duc99dilt
Syntax:
-dontusec99decintlittypes[{+|-}]
Default:
-dontusec99decintlittypes+
Category:
Advanced
Function:
When -dontusec99decintlittype is disabled, the first type large enough from 'int', 'long' and 'long long'
when determining the size of an unsuffixed literal.
Page 189


---
*Page 189*

Literals with values greater than LONG_MAX have 'long long' type according to the 2011 ISO Standard. However, some
older compilers may treat such literals as 'unsigned long'.
Note:
The option is so named as C99 was the first ISO standard to adopt the 'long long' type and define the
rules for it.
For Example:
void foo(int i);
void foo(unsigned long ul);
void test_duc99dilt_OFF()
{
//
// qac++ uses long long as the type of literal in accordance
// with the C99 standard
//
// ambiguous: no overload with an argument long long
// and the conversions to unsigned long and int are equal
foo(4294967295); // ambiguous
}
void test_duc99dilt_ON()
{
//
// qacpp uses unsigned long as the type for the literal
//
// therefore foo(unsigned long) is chosen from the overload set
foo(4294967295); // calls foo(unsigned long)
}
Page 190


---
*Page 190*

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
The term "dataflow analysis" refers to a range of techniques in which static analysis of source code is used to analyze
run-time behavior of a program. Dataflow analysis can identify a class of problems which may range from serious issues
such as undefined behavior to conditions which are of interest simply because they are frequently associated with coding
errors.
See the Dataflow manual for more information.
-encoding,-en
Syntax:
-encoding encoding
Default:
no entry
Category:
Basic
Function:
Specifies the character set of the source file being analyzed.
The analyzer has the ability to read files encoded with many different character sets. The name of the character set to
use for a given file can be specified using the -encoding option.
Note:
The encoding option is ignored for source files that use a Byte Order Mark (BOM). These files will always
be read using using the UTF variant specified by the BOM.
Page 191


---
*Page 191*

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
Character sets may also have variants not listed, for example: ISO-8859-14, windows-1250, UTF-32LE,
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
Page 192


---
*Page 192*

The function specified by function will be considered to set errno and so may result in messages warning that errno has
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
Page 193


---
*Page 193*

The function specified by function will be considered to return a value representing a success flag or error status. If it is
not checked immediately, a warning will be emitted.
For example:
void foo(void)
{
extern int bar (void);
bar(); // Generates a warning with -errorstatusreturningfunction bar
if (bar () == 0) { } // No warning, error status checked
}
If a number is specified in parentheses immediately after the name, it is interpreted as the index (starting from 1) of an
out-parameter which stores error status, rather than the return value itself:
void foo2(void)
{
extern void baz (int * status, int value);
int status1;
baz (&status1, 42); // Generates a warning with
// -errorstatusreturningfunction "baz(1)"
int status2;
baz (&status2, 42); // No warning, status2 checked
if (status2 == 0) { }
Page 194


---
*Page 194*

}
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
Page 195


---
*Page 195*

The following options are cumulative in Helix QAC for C++:
n -nomsg,-no,-n
n -only,-o
n -quiet,-q
n -i
n -systeminclude,-si
n -d
n -systemdefine,-sd
n -warncall,-wc
n -warnmacroexpansion,-wme
n -warnkeyword,-wk
n -warnpragma,-wp
n -warnset,-ws
n -quietextended,-qx
-prodoption format::printf
Syntax:
-prodoption format::printf=characters
Default:
no entry
Category:
Basic
Function:
Specifiers to be supported by 'printf' checking.
Page 196


---
*Page 196*

This option lists the specifiers that are considered valid in the format string passed to printf.
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
-prodoption format::scanf=characters
Default:
no entry
Category:
Basic
Function:
Specifiers to be supported by 'scanf' checking.
Page 197


---
*Page 197*

This option lists the specifiers that are considered valid in the format string passed to scanf.
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
-help,-h
Syntax:
-help[{+|-}]
Default:
-help-
Category:
Internal
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
Page 198


---
*Page 198*

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
Page 199


---
*Page 199*

A common technique for handling non-standard extensions is to define the expansion of identifiers to nothing so they do
not appear in the preprocessed source code. A force include header can be used to achieve this:
/* forceinclude.h */
#define __extension__
/* main.cc */
int i = __extension__ 0;
Running with -fi forceinclude.h allows the code to be parsed successfully. A slight complication occurs when the -
rememberfirstdefinedirective option is disabled. This can result in user code changing what the macro expands to and
making invalid the workaround in the force include header:
/* main.cc */
#define __extension__ __OTHER_EXTENSION__
int i = __extension__ 0;
In order to ensure that the required workaround will always be used, irrespective of the -rememberfirstdefinedirective
setting, then the _ignore_modification feature of -d can be used to fix the value that the macro expands to:
/* forceinclude.h */
#define __extension__
#define __extension__ _ignore_modification  /* expansion fixed */
#define __extension__ 0                     /* no effect */
When -po ignore_modification::forceinclude is enabled, all macros in the force include file will implicitly be treated as also
being defined with _ignore_modification.
Page 200


---
*Page 200*

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
A common technique for handling non-standard extensions is to define the expansion of identifiers to nothing so they do
not appear in the preprocessed source code:
/* main.cc */
int i = __extension__ 0;
Running with -systemdefine "__extension__=" allows the code to be parsed successfully. A slight complication
occurs when -rememberfirstdefinedirective option is disabled. This can result in user code changing what the macro
expands to and making invalid the workaround in the force include header:
/* main.cc */
#define __extension__ __OTHER_EXTENSION__
int i = __extension__ 0;
In order to ensure that the required workaround will always be used, irrespective of the -rememberfirstdefinedirective
setting, then the _ignore_modification feature of -d and -sd can be used to fix the value to which the macro expands: -
systemdefine "__extension__=" -systemdefine "__extension__=_ignore_modification" .
When -po ignore_modification::systemdefine is enabled, all macros specified using -systemdefine (-sd) will implicitly be
treated as also being defined with _ignore_modification.
See also _ignore_modification in -d, -rememberfirstdefinedirective,-remfdd and -prodoption ignore_
modification::forceinclude.
Page 201


---
*Page 201*

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
-prodoption inline_cost::bin_expr
Syntax:
-prodoption inline_cost::bin_expr=cost
Default:
-prodoption inline_cost::bin_expr=1
Category:
Basic
Function:
The pseudo cost of a binary expression (non overloaded).
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::builtin_init
Syntax:
-prodoption inline_cost::builtin_init=cost
Default:
-prodoption inline_cost::builtin_init=0
Category:
Basic
Function:
The pseudo cost of a built-in initializer.
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::cast_expr
Syntax:
-prodoption inline_cost::cast_expr=cost
Default:
-prodoption inline_cost::cast_expr=1
Category:
Basic
Function:
The pseudo cost of a cast expression that doesn't call a constructor.
Page 202


---
*Page 202*

This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::cond_expr
Syntax:
-prodoption inline_cost::cond_expr=cost
Default:
-prodoption inline_cost::cond_expr=1
Category:
Basic
Function:
The pseudo cost of a ternary expression.
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::conv_expr
Syntax:
-prodoption inline_cost::conv_expr=cost
Default:
-prodoption inline_cost::conv_expr=1
Category:
Basic
Function:
The pseudo cost of a conversion expression that doesn't call a constructor.
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::do_stmt
Syntax:
-prodoption inline_cost::do_stmt=cost
Default:
-prodoption inline_cost::do_stmt=2
Category:
Basic
Function:
The pseudo cost of a do statement.
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::dyn_cast_expr
Syntax:
-prodoption inline_cost::dyn_cast_expr=cost
Default:
-prodoption inline_cost::dyn_cast_expr=4
Category:
Basic
Function:
The pseudo cost of a dynamic cast expression that doesn't call a constructor.
This option only applies in conjunction with the -prodoption inline_cost::max option.
Page 203


---
*Page 203*

-prodoption inline_cost::for_stmt
Syntax:
-prodoption inline_cost::for_stmt=cost
Default:
-prodoption inline_cost::for_stmt=2
Category:
Basic
Function:
The pseudo cost of a for statement.
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::goto_stmt
Syntax:
-prodoption inline_cost::goto_stmt=cost
Default:
-prodoption inline_cost::goto_stmt=1
Category:
Basic
Function:
The pseudo cost of a goto statement.
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::if_stmt
Syntax:
-prodoption inline_cost::if_stmt=cost
Default:
-prodoption inline_cost::if_stmt=1
Category:
Basic
Function:
The pseudo cost of an if statement.
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::max
Syntax:
-prodoption inline_cost::max=limit
Default:
no entry
Category:
Basic
Function:
Sets the maximum value of an algorithm measuring the cost of a function that may be inlined.
Page 204


---
*Page 204*

For example:
inline int foo (int k)
// Inline cost of 4
{
int j = k;
// 1
if (k > 0)
// 1
{
++j;
// 1
}
else
{
--j;
// 1
}
return j;
}
Further explanation and details on the generation of the algorithm can be found in the help for message 4125.
Note:
This option must be set for analysis of the cost of inline functions to take place.
-prodoption inline_cost::non_virtual_call
Syntax:
-prodoption inline_cost::non_virtual_call=cost
Default:
-prodoption inline_cost::non_virtual_call=2
Category:
Basic
Function:
The pseudo cost of making a non virtual call.
This option only applies in conjunction with the -prodoption inline_cost::max option.
Page 205


---
*Page 205*

-prodoption inline_cost::throw_expr
Syntax:
-prodoption inline_cost::throw_expr=cost
Default:
-prodoption inline_cost::throw_expr=2
Category:
Basic
Function:
The pseudo cost of a throw expression.
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::try_stmt
Syntax:
-prodoption inline_cost::try_stmt=cost
Default:
-prodoption inline_cost::try_stmt=4
Category:
Basic
Function:
The pseudo cost of a try statement.
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::uny_expr
Syntax:
-prodoption inline_cost::uny_expr=cost
Default:
-prodoption inline_cost::uny_expr=1
Category:
Basic
Function:
The pseudo cost of a unary expression (excluding '()' and '+').
This option only applies in conjunction with the -prodoption inline_cost::max option.
-prodoption inline_cost::virtual_call
Syntax:
-prodoption inline_cost::virtual_call=cost
Default:
-prodoption inline_cost::virtual_call=4
Category:
Basic
Function:
The pseudo cost of making a virtual call.
This option only applies in conjunction with the -prodoption inline_cost::max option.
Page 206


---
*Page 206*

-prodoption inline_cost::while_stmt
Syntax:
-prodoption inline_cost::while_stmt=cost
Default:
-prodoption inline_cost::while_stmt=2
Category:
Basic
Function:
The pseudo cost of a while statement.
This option only applies in conjunction with the -prodoption inline_cost::max option.
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
underlying type to use for enumerations. Allows wchar_t to be modelled as an alias to a type rather than a keyword and a
distinct type.
For -intrinsictype "size_t=...", -intrinsictype "ptrdiff_t=...", and -intrinsictype "wchar_t=...", a single built-in type name is
specified to use as the underlying type. Helix QAC for C++ will generate a level 9 warning if these are not consistent with
any typedef settings encountered in the source code.
For -intrinsictype "enum=...", a sequence of basic data types is specified in a comma-separated list. For each enum
definition, Helix QAC for C++ determines the minimum and maximum value of the enumerators used to define the enum
type. Starting with the first entry in this list, the first type large enough to hold all the enum's values will be selected as the
underlying type.
-introducefriendnames,-ifn
Syntax:
-introducefriendnames[{+|-}]
Default:
-introducefriendnames-
Category:
Advanced
Function:
When enabled, friend names are introduced into the nearest enclosing namespace.
Page 207


---
*Page 207*

According to the ISO Standard, a name introduced by a friend declaration will only be found through argument
dependent (Koenig) lookup. When -introducefriendnames is enabled, friend names will be visible to all name lookups.
For example:
class A
{
public:
friend void foo ();
};
void bar ()
{
// Succeeds with -introducefriendnames+
foo ();
}
-iso646keywords,-iso646kw
Syntax:
-iso646keywords[{+|-}]
Default:
-iso646keywords+
Category:
Advanced
Function:
When disabled, the C++ alternative tokens are not treated as keywords in C++.
Page 208


---
*Page 208*

In C++, the alternative tokens are also keywords and shall not be used otherwise. In C, these tokens are identifiers that,
through including files, can be given appropriate replacement values.
The alternative tokens are:
n and &&
n and_eq &=
n bitand &
n or ||
n or_eq |=
n bitor |
n xor ^
n xor_eq ^=
n compl ~
n not_eq !=
n not !
In addition to the above, C++ also requires special handling of true and false when evaluating the result of #if
directives.
const int J = 6 bitand 5;
// J gets the result 4 (6 & 5)
const int K = 1 bitor 8;
// K gets the result 9 (1 | 8)
-layoutfile,-lf
Syntax:
-layoutfile file
Default:
no entry
Category:
Advanced
Function:
Specifies the location of the file to be used to configure the code layout engine.
Page 209


---
*Page 209*

It is good practice, and often part of programming standards or guidelines to keep indentation consistent, to make it
easier to read the code and follow the logic. The analyzer allows you to enforce the layout of your code by checking for
consistent brace style, indentation, and spacing of your code. Warnings are generated if the layout is not consistent.
This option allows you to specify the layout configuration file that best matches your layout style. Three layout
configuration files are shipped by default, exdented.layout, indented.layout, and knr.layout, which enforce the following
bracing styles:
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
There are also three other files, exdented-spacing.layout, indented-spacing.layout, and knr-spacing.layout, which, in
addition to above bracing rules, also contain spacing rules that are considered to be "tolerant". Thus, any reasonable
amount of spacing within your source code is allowed.
-layoutignoreheaders,-lih
Syntax:
-layoutignoreheaders[{+|-}]
Default:
-layoutignoreheaders-
Category:
Advanced
Function:
When enabled, code layout within header files will not be checked when performing layout analysis.
Page 210


---
*Page 210*

-layoutindentwidth,-liw
Syntax:
-layoutindentwidth value
Default:
-layoutindentwidth 0
Category:
Advanced
Function:
This sets the number of spaces to be used when indenting code.
When performing layout analysis, QAC++ will issue a warning message if the code indentation differs from this value. If
this option is not set, or if it set to 0, message 1982 will be generated.
-layoutusehangingindent,-luhi
Syntax:
-layoutusehangingindent[{+|-}]
Default:
-layoutusehangingindent-
Category:
Advanced
Function:
When enabled, statements that follow labels are required to be indented during layout checking.
A common layout style for labels is to indent all statements after a label using the label as the indent base.
When -layoutusehangingindent is enabled, the analyzer will warn if any statements that follow a label are not indented
from the label. Otherwise, the analyzer will only enforce indentation on the statement immediately following the label,
relative to the switch statement.
switch (value)
{
case 1: // the switch label
  statement; // OK with -layoutusehangingindent+
break;
}
-prodoption line::max_length
Syntax:
-prodoption line::max_length=limit
Page 211


---
*Page 211*

Default:
no entry
Category:
Basic
Function:
Sets the maximum permissible width of a line in characters.
If the length of a line exceeds limit, then message 1094 will be generated:
1094 This source line is longer than 'limit' characters.
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
Function:
Determines the number of hard errors that will cause the analysis to stop.
The default of zero indicates that the parser will attempt to continue to completion regardless of hard errors encountered.
The parser will issue return code 1 when any hard errors are encountered. This setting merely decides whether parsing
will continue to source completion.
-maxmacrohistory,-maxmh
Syntax:
-maxmacrohistory value
Default:
-maxmacrohistory 8192
Category:
Advanced
Function:
Limit on the number of entries to store in the macro expansion history of a source location.
Page 212


---
*Page 212*

By default, history information is stored for tokens expanded from macros in order to provide better location reporting and
to perform some analyses of library objects defined as macros. However, this can use up a lot of storage if macros are
heavily used to create nested expansions.
Only the specified number of history entries will be stored. If macro expansion is more deeply nested, preprocessing
itself will not be affected, but the "expanded from here" history will not be available for error reporting. Some analyses
that check whether an expression originates from a macro may fail to work if the expression is produced at an
unrecorded level of nesting.
If zero is the value specified, no macro history will be recorded at all. This may be useful for some machine-generated
files. The value is always zero for expansions originating in quieted headers.
This limit can also be adjusted within a file by means of the PRQA_MAX_MACRO_HISTORY pragma. This may be useful
when a certain section within a TU uses deep nesting.
#define D NULL
#define C D
#define B C
#define A B
void * p1 = A;
// if -maxmacrohistory is less than 5, this will be seen as '=
0'
void * p2 = NULL; // if -maxmacrohistory is zero, this will be seen as '= 0'
// set the macro history length limit to 3, regardless of previous options
#pragma PRQA_MAX_MACRO_HISTORY 3
// change the macro history length limit to 8
#pragma PRQA_MAX_MACRO_HISTORY 8
-maxrecursivetemplatenestingdepth,-mrtnd
Syntax:
-maxrecursivetemplatenestingdepth value
Default:
-maxrecursivetemplatenestingdepth 200
Category:
Advanced
Function:
Specifies the maximum depth that is allowed for recursive instantiations of templates.
Page 213


---
*Page 213*

For example:
template <unsigned int I>
struct B
{
static const unsigned int value = B<I+1>::value;
};
template <>
struct B<201>
{
static const unsigned int value = 0;
};
void foo ()
{
  B<0> b;
}
If reached, an explicit specialization of B with 201 would stop the recursive template instantiation. However, this could
use a large amount of resources and time.
The -maxrecursivetemplatenestingdepth option can be used to increase or decrease the depth that a recursive
instantiation will reach before being stopped.
-prodoption metrics::no_do_while
Syntax:
-prodoption metrics::no_do_while[{+|-}]
Default:
-prodoption metrics::no_do_while+
Category:
Basic
Page 214


---
*Page 214*

Function:
Controls whether do..while loops with an integer constant zero loop condition are counted as control
structures.
A do..while loop with a constant zero as the loop controlling expression will only be executed once and is generally
similar to a simple braced compound expression. It does not introduce algorithmic complexity and is normally introduced
by macros purely for block scope purposes. Therefore, it is not counted as part of control flow metrics by default.
Loops that make use of a break or continue statement will still be counted as their loop structure is relevant.
-namerulefile,-nrf
Syntax:
-namerulefile filename
Default:
no entry
Category:
Basic
Function:
Specifies the file containing the naming convention rules to be applied by namecheck.
The name rules file contains the rules to be used by the Name Checker. As a minimum, each rule should specify the
pattern (Regular Expression) that is to be applied to each type of identifier (macros, functions, typedefs, variables, etc).
You can have different rules for different types of identifier.
See the Configuration File section of the Namecheck user manual.
-prodoption namespace::max_depth
Syntax:
-prodoption namespace::max_depth=limit
Default:
no entry
Category:
Basic
Function:
Sets the maximum depth of namespace (excluding unnamed namespaces).
If the nesting depth of namespaces exceeds limit, then message 2517 will be generated.
2517 This namespace is nested more than 'limit' levels deep.
-nestedcomments,-nc
Syntax:
-nestedcomments[{+|-}]
Default:
-nestedcomments-
Category:
Advanced
Function:
When enabled, nesting of C-style comments are tracked.
Page 215


---
*Page 215*

C-style comments do not nest, the first comment end sequence to appears in a source file is therefore the end of the
comment, irrespective of how many open sequences appeared.
For Example:
/*    Start of C Comment
/* Start of "nested" Comment
End of nested Comment  */
Error this text is not commented */
When -nestedcomments+ is enabled, the number of C-style open sequences will be tracked and then matched with the
closing sequence count, resulting in the above being considered as all comments.
-newarraycookiesize,-nacs
Syntax:
-newarraycookiesize bytes
Default:
-newarraycookiesize -1
Category:
Advanced
Function:
Set the size of the new array cookie. The default value of -1 will result in cookie size being set to 'size_t'
The size in bytes of the overhead required by array new expressions can be set with this option. Different compilers may
need different sizes and should be found in the compiler implementation documentation. The overhead size (commonly
referred to as cookie size) defaults to size_t.
Note:
This option is applicable to Dataflow analysis of C++ only.
-nodigraphmodglobalnamespace,-ndmgns
Syntax:
-nodigraphmodglobalnamespace[{+|-}]
Default:
-nodigraphmodglobalnamespace-
Page 216


---
*Page 216*

Category:
Advanced
Function:
When enabled, the sequence %:: will be usable in an expression.
The 2011 ISO Standard changed the way digraph tokens are read, adding an exception for the <: when it is followed by
another : that is not itself part of a longer following token.
For consistency with the handling of <, this option allows the same exception to be applied to %. This is a non-standard
extension; the ISO Standard only specifies the exception for <.
For Example:
int x;
bool mod_x (int y)
{
return y%::x; // without this option, expression would be read as y#:x
}
-nomsg,-no,-n
Syntax:
-nomsg message_number_list
Default:
no entry
Category:
Non-component
Function:
Suppresses the display and generation of the specified messages.
Message numbers can be specified individually, or as a list, range or a combination of both:
n -nomsg 2356
n -nomsg 1234,1236,1240
n -nomsg 2111,2200-2300
Note:
This option is only available at the file or directory level. The enabling or disabling of diagnostics at the
component level is managed through the Rule Configuration File (RCF).
This option is cumulative. See -forgetall,-forget,-f.
Page 217


---
*Page 217*

-noseparateargexpandedcomma,-nsaec
Syntax:
-noseparateargexpandedcomma[{+|-}]
Default:
-noseparateargexpandedcomma-
Category:
Advanced
Function:
When enabled, an expanded comma is not treated as an argument separator in a macro expansion.
For example:
#define COMMA ,
#define FUNC0(A, X, B) A X B
#define FUNC1(A, X, B) FUNC0(A, X, B)
#define FUNC2(A, B) FUNC1(A, COMMA, B)
void foo()
{
// Succeeds with -noseparateargexpandedcomma+
FUNC2(1 , 2);
}
-only,-o
Syntax:
-only message_number_list
Default:
no entry
Category:
Non-component
Function:
Only the specified warning messages will be generated.
Page 218


---
*Page 218*

Message numbers can be specified individually, or as a list, range or a combination of both:
n -only 2356
n -only 1234,1236,1240
n -only 2111,2200-2300
Note:
This option is only available at the file or directory level. The enabling or disabling of diagnostics at the
component level is managed through the Rule Configuration File (RCF).
This option is cumulative. See -forgetall,-forget,-f.
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
-prodoption pass_by_value::max_size
Syntax:
-prodoption pass_by_value::max_size=limit
Default:
no entry
Category:
Basic
Function:
Sets the maximum permissible size (in bytes) for a pass-by-value function parameter with a user-
declared type. This analysis is only performed for function definitions.
Message 2010 is generated for user-declared parameter types if the 'pass_by_value' option is not specified, or if the size
of the parameter type is less than max_size.
Message 2009 is generated if max_size is exceeded and the function parameter type can be changed to pass the
parameter as a 'const &'.
Message 2008 is generated if max_size is exceeded and the function parameter type cannot be changed as the
parameter is modified in the function body.
-ppfilename,-ppf
Syntax:
-ppfilename[{+|-}]
Page 219


---
*Page 219*

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
Page 220


---
*Page 220*

Output files will only contain information generated from the preprocessing stage:
n file metrics,
n implicit declarations,
n macros, and
n preprocessor messages.
This option can be used for analysis debug purposes, specifically to determine that preprocessing completes without
engaging in C++ parsing and analysis.
-preproc32bittype,-pp32bt
Syntax:
-preproc32bittype[{+|-}]
Default:
-preproc32bittype-
Category:
Advanced
Function:
When enabled, preprocessor integral evaluation is performed using 32-bit arithmetic rather than the ISO
Standard default of 64-bit arithmetic.
For example:
// Condition true with -preproc32bittype+
#if ((1<<31)<0)
#error "Preprocessor calculation in 32 bits"
#endif
-preproccppkeywords,-ppcppkw
Syntax:
-preproccppkeywords[{+|-}]
Default:
-preproccppkeywords+
Category:
Advanced
Function:
When enabled, the C++ alternative tokens are treated as keywords in the preprocessor.
Page 221


---
*Page 221*

In C++, the alternative tokens are also keywords and shall not be used otherwise. In C, these tokens are identifiers that,
through including files, can be given appropriate replacement values.
The alternative tokens are:
n and &&
n and_eq &=
n bitand &
n or ||
n or_eq |=
n bitor |
n xor ^
n xor_eq ^=
n compl ~
n not_eq !=
n not !
In addition to the above, C++ also requires special handling of true and false when evaluating the result of #if
directives.
#if defined (and)  // Identifier expected
#endif
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
-propagatetemplateparameters,-ptp
Syntax:
-propagatetemplateparameters[{+|-}]
Page 222


---
*Page 222*

Default:
-propagatetemplateparameters-
Category:
Advanced
Function:
When enabled, template parameter names from primary template definitions are made available to
template specialization definitions.
For example:
template <typename T>
class A { };
template <>
class A<int>
{
public:
// Succeeds with -propagatetemplateparameters+
  T foo (T); // T is 'int'
};
-prodoption qax::limit
Syntax:
-prodoption qax::limit=size(KB)
Default:
-prodoption qax::limit=30
Category:
Advanced
Function:
Sets the maximum packet size in KB sent to the QAX daemon.
Page 223


---
*Page 223*

The following information is sent by the analysis tools to the QAX daemon:
n Filenames
n Locations
n Preprocessor Events
n Diagnostics
n Annotations
n Function Flow Graphs.
This option controls the amount of data stored before being transmitted to the server.
In general this option does not need to be changed, however, if investigating a failure with the tool, it can be useful to set
the option to 0 in order that all data is sent immediately to the daemon.
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
This will have the effect of suppressing warning messages as well as significantly reducing the size of the output
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
Page 224


---
*Page 224*

This will have the effect of suppressing warning messages as well as significantly reducing the size of the output
produced. This suppression is limited to constructs from those files/folders that are not used in non suppressed files.
When the argument is a non-absolute path, the path is interpreted to be a regular file path relative to a -systeminclude
path. If the concatenation of a system include path and the relative file path corresponds to an existing file, the option
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
Page 225


---
*Page 225*

The argument to this option should be a mangled name referring to a function followed immediately by a number in
parentheses.
The specified function will be treated as a function that initialises a RNG.
The number specified in parentheses immediately after the name, is interpreted as the index (starting from 1) of the
parameter which contains the new seed being used to configure the RNG.
It is the value of the seed parameter that is analysed to see if it is unchanging or predictable.
For example:
const int SEED=1;
void foo(void)
{
Random_Init(SEED);
// Generates diagnostics with -rngs="Random_Init(1)"
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
  rng.init(SEED);
// generates diagnostics with -rngs=".QN7SeedCtxN4initPi(1)"
Page 226


---
*Page 226*

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
Page 227


---
*Page 227*

The default behavior of the analyzer is to issue a message and update the replacement list of a macro for each new
#define directive:
#define A 1     /* A's replacement list set to 1 */
#define A 2     /* Message generated to highlight that macro A has been
/* redefined and A's replacement list changed to 2 */
int i = A;
/* A expands to 2 */
Previous versions operated slightly differently in that a message was issued but the replacement list was not changed:
#define A 1     /* A's replacement list set to 1 */
#define A 2     /* Message generated to highlight that macro A has been
/* redefined and A's replacement list unchanged as 1 */
int i = A;
/* A expands to 1 */
The -rememberfirstdefinedirective option can be used to revert the behavior to match the previous functionality.
Note:
Macros defined on the command line always use the last value.
See also _ignore_modification in -d, -systemdefine,-sd, -prodoption ignore_modification::systemdefine and -prodoption
ignore_modification::forceinclude.
-rvaluerefbind,-rvrb
Syntax:
-rvaluerefbind[{+|-}]
Default:
-rvaluerefbind+
Category:
Advanced
Page 228


---
*Page 228*

Function:
When enabled, temporary class types are directly bound to const references, rather than calling a copy
constructor.
In the 2003 ISO C++ Standard it was implementation defined if a temporary was first copied, and the copy then bound to
the reference.
For example:
template <typename T> struct A
{
A ();
A (A const &)
{
typedef typename T::copy_not_needed_for_ref_bind TYPE;
}
};
void bar(A<int> const &);
void foo ()
{
// Succeeds with -rvaluerefbind+
bar ( A<int>() );
}
-searchdependentbaseclasses,-sdep
Syntax:
-searchdependentbaseclasses[{+|-}]
Default:
-searchdependentbaseclasses-
Category:
Advanced
Page 229


---
*Page 229*

Function:
When enabled, non standard lookup is performed in dependent base class scope.
For some compilers, an identifier looked up in a class template may be found in a base class that is a dependent type.
This lookup is not standard behavior, however the analyzer attempts to find names in the primary class template where a
definition is available.
For example:
template <typename T> struct A
{
typedef int TYPE;
};
template <typename T> struct B : public A<T>
{
void foo ()
{
// Succeeds with -searchdependentbaseclasses+
    TYPE t;
}
};
-settings,-set
Syntax:
-settings[{+|-}]
Default:
-settings-
Category:
Internal
Function:
Print the settings used by the tool after the complete processing of all command line arguments.
When enabled, the current values for all configuration options are listed to the standard output.
Page 230


---
*Page 230*

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
The analyzer uses type size values to calculate the size of structures and to perform analysis.
The available size and alignment values are constrained by the ISO Standard rules on integral size ordering. The size is
often related to the alignment of a data type.
See -align,-a for the full set of constraints on size and alignment.
-slashwhite,-sl
Syntax:
-slashwhite[{+|-}]
Default:
-slashwhite-
Category:
Advanced
Function:
When enabled, parsing ignores whitespace between \ and the end of a line.
Some source code uses continuation lines that have whitespace between the \ and the end of the line. This can happen
when source files are transferred between different operating systems and results in errors, unless this option is enabled.
-stdisglobal,-sig
Syntax:
-stdisglobal[{+|-}]
Default:
-stdisglobal-
Category:
Advanced
Function:
When enabled, declarations in namespace std are treated as if they were declarations in the global
scope, and also declarations in the global scope treated as if they were declarations in namespace std.
Page 231


---
*Page 231*

Some older non standard compilers treated the global scope and namespace std as the same. This option can be used
to match this non standard behavior.
For example:
void foo ();
namespace std
{
void bar ();
}
void car ()
{
// Both examples succeed with -stdisglobal+
  std :: foo ();
// OK, although foo() not declared
// in std
bar ();
// OK, although bar() not declared
// in global scope
}
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
This is disabled by default, which means that the parser will continue to completion regardless of any hard errors
encountered.
Page 232


---
*Page 232*

-stripemptyvaargcomma,-sevac
Syntax:
-stripemptyvaargcomma[{+|-}]
Default:
-stripemptyvaargcomma-
Category:
Advanced
Function:
When enabled, preceding commas are removed if the __VA_ARGS__ parameter expands to nothing.
For example:
void call( const char * );
#define TEST1(format, ...) call( format, __VA_ARGS__ )
void f1 ()
{
TEST1("test1");
// Expands to "call( "test1",  )"  with -stripemptyvaargcomma-
// Expands to "call( "test1"   )"  with -stripemptyvaargcomma+
}
-prodoption switch::min_cases
Syntax:
-prodoption switch::min_cases=limit
Default:
no entry
Category:
Basic
Function:
Sets the minimum number of cases that should exist before a switch statement with a single case block
is considered better than an if-statement.
If the number of case labels in a switch is non zero, and is less than or equal to limit, then message 4018 will be
generated:
4018 An if statement would provide a more natural representation instead
of this switch.
Page 233


---
*Page 233*

-systemdefine,-sd
Syntax:
-systemdefine ident[=[value]]
Default:
no entry
Category:
Basic
Function:
Defines system macros.
System macros in the analyzer have the same value and semantics as -d except that they are processed after the -d
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
Directories specified with the -systeminclude option have the same value and semantics as those specified using -i,
except that these directories will be searched after the directories specified with -i.
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
Tab spacing is not related to the depth of indentation. It does affect the column location used when issuing diagnostics
against the source file.
See -layoutindentwidth,-liw for analysis related to depth of indentation.
-thirdparty,-tp
Syntax:
-thirdparty[{+|-}]
Default:
-thirdparty-
Page 234


---
*Page 234*

Category:
Non-component
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
The metric is specified by the name that appears in the metrics records of the .arc file. There are no default values. If
:msg_no is omitted the default analyzer message 4700 will be used.
The optional prefix_ can be used to specify the Compliance Module that msg_no is associated with.
See Metric Thresholds and Metric Output File for more information.
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
The -undef option when specified will causes the removal of definitions of ident previously seen on the command line.
For example if the sequence:
-d "A=1" -d "B=2" -d "c=3" -undef B
Will have the same affects as:
-d "A=1" -d "c=3"
Page 235


---
*Page 235*

The -undef option applies to both the -d and -systemdefine,-sd options equally, and so entries in both lists will be affected
by the option.
For example if the sequence results in no macros being processed by Helix QAC for C++:
-d "A=1" -sd "B=2" -undef B -undef B
See the -d option for information on replacement lists with special meaning.
-url
Syntax:
-url url
Default:
no entry
Category:
Internal
Function:
The URL of the server to which analysis data should be sent.
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
Page 236


---
*Page 236*

Before analysis is performed by a component a limit is set on the amount of memory that the component can utilise. By
default this limit is set to either a percentage of the systems physical memory or a default fixed size, whichever is largest.
This option determines the limit placed on the memory available to the component during analysis as a percentage of the
total systems memory.
If the argument of this option is 0 then no memory limit is applied to the component. And if the value of the argument does
not lie between 0 and 100 then the default limit will be applied.
-warncall,-wc
Syntax:
-warncall function[=[prefix_]msg_no]
Default:
no entry
Category:
Advanced
Function:
Displays warning message msg_no if a call to function is encountered.
If no message number is specified for C, the following default message is displayed:
2010 The function 'func_name' must not be called.
If no message number is specified for C++, the following default message is displayed:
3999 Function 'func_name' called.
When msg_no is specified, the optional prefix_ can be used to specify the Compliance Module that msg_no is
associated with.
Note:
When function is specified to be @destructor only explicit destructor calls, such as p->T(), will result
in a message.
This option is cumulative, see -forgetall,-forget,-f.
-warnkeyword,-wk
Syntax:
-warnkeyword keyword[=[prefix_]msg_no]
Default:
no entry
Category:
Advanced
Function:
Displays diagnostic message msg_no if usage of keyword is encountered.
If no message number is declared, then message 1080 is displayed:
1080 Using keyword 'keyword_name'.
When msg_no is specified, the optional prefix_ can be used to specify the Compliance Module that msg_no is
associated with.
This option is cumulative, see -forgetall,-forget,-f.
Page 237


---
*Page 237*

-warnmacroexpansion,-wme
Syntax:
-warnmacroexpansion macro[=[prefix_]msg_no]
Default:
no entry
Category:
Advanced
Function:
Displays warning message msg_no if a macro is expanded.
If no message number is declared, the following message is displayed:
1007 The macro 'macro_name' must not be expanded.
This option ignores any message number which is not between 1 and 9998 inclusive.
When msg_no is specified, the optional prefix_ can be used to specify the Compliance Module that msg_no is
associated with.
This option is cumulative, see -forgetall,-forget,-f.
-warnpragma,-wp
Syntax:
-warnpragma pragma[*][=0|[prefix_]msg_no]
Default:
no entry
Category:
Advanced
Function:
Displays diagnostic message msg_no if a #pragma directive that matches pragma is encountered.
The entry -warnpragma pragma=0 causes no diagnostic to be generated, and allows you to isolate necessary #pragma
directives in code. The option can include the use of wildcards. Options can overwrite previous entries.
When msg_no is specified, the optional prefix_ can be used to specify the Compliance Module that msg_no is
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
Page 238


---
*Page 238*

Note: in C++ the qualified_member_name must be specified using the mangled name format.
If no message number is specified for C, the following default message is displayed:
2033 The member 'member_name' must not be set.
If no message number is specified for C++, the following default message is displayed:
3998 Member variable 'member_name' modified.
Warning Messages and Context
Each -warnset may specify up to three warning messages per fully qualified member name.
The first is the message to be raised if the member is set "implicitly". For example, if the non-static data member has a
default value, and no other value is provided during construction of an object, the implicit_msg_no will be raised.
// QAC  : -warnset A::value -warnset A::seed=5001
// QAC++: -warnset .QNAN5value -warnset .QNAN4seed=5001
struct A
{
int value =
1;
// default message raised
int seed = 1;
// 5001 raised
};
Page 239


---
*Page 239*

The second is the message to be raised if the member is explicitly set to a compile-time constant value (i.e. a value which
does not change between program runs). For example: passing a literal value to a member during construction will result
in the explicit_const_msg_no being raised.
// QAC  : -warnset A::value -warnset A::seed=5001,5002
// QAC++: -warnset .QNAN5value -warnset .QNAN4seed=5001,5002
typedef struct
{
int value;
int seed;
} A;
A a {0,
// default raised
0};
// 5002 raised
Page 240


---
*Page 240*

Finally, the third is the message to be raised if the member is explicitly set to a dynamic value (i.e. a value that is different
every time the program runs). For example: passing the return value of a function call to a member during construction
will result in the explicit_nonconst_msg_no being raised.
// QAC  : -warnset A::value -warnset A::seed=5001,5002,5003
// QAC++: -warnset .QNAN5value -warnset .QNAN4seed=5001,5002,5003
typedef struct
{
unsigned value;
unsigned seed;
} A;
unsigned getInitValue();
unsigned getInitSeed();
A a {getInitValue(),
// default raised
getInitSeed()};
// 5003 raised
If at least one message number is specified but not all the messages are specified, then any that are unspecified will be
ignored.
!filtervalue
The first two msg_no values can optionally take a "filter value". In the 2021.3 release this is an integer value that
represents a single "valid" integer value. If analysis detects that the member is being to set to anything other than the
"filter value" then the associated msg_no will be raised.
Page 241


---
*Page 241*

The command line uses "!" to specify "not <filter_value>". The associated msg_no will be raised if qualified_member_
name is set to a value that is not <filter_value>.
// QAC  : -warnset A::value=5001!1,5002!1,5003
// QAC++: -warnset .QNAN5value=5001!1,5002!1,5003
typedef struct
{
unsigned value = 0;
// 5001 raised
} A;
A a_bad {128};
// 5002 raised
A a_ok  {1};
// 5002 NOT raised
When at least one message number is specified, the optional prefix_ can be used to specify the Compliance Module
that all messages are associated with.
This option is cumulative, see -forgetall,-forget,-f.
Page 242


---
*Page 242*
