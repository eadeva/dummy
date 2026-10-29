# 6 | Essential Types

6 | Essential Types
Introduction
Helix QAC for C uses an extensive range of messages associated with type usage and type conversion. These
messages are based on the concept of essential type as described in this user guide.
MISRA C
In the MISRA C:2004 Guidelines, several terms were introduced in an attempt to describe the essential nature of an
arithmetic expression in a way that the ISO-C language standard does not provide. These terms were:
 n Underlying type
 n Effectively Boolean
 n Complex expression
Although these concepts have been found useful, a number of weaknesses have been identified:
 1. The term underlying type is used already in a different sense in the C++ standard to describe the implementation
of enum types.
 2. The term complex is a source of confusion, being more obviously associated with the algebra of complex
numbers - and hence complex floating types within the C language.
 3. The definition of underlying type was not specified with sufficient rigour.
 4. The concept of underlying type did not address the whole range of integer data types - such as character data,
enum data, Boolean data and bit-fields.
The Essential Type Concept
The essential type concept has evolved from the concept of underlying type with the intention of addressing some of the
problems referred to above. It provides an alternative way of describing the essential characteristics of objects, constants
and expressions of arithmetic type.
The term essentially Boolean now supersedes the term effectively Boolean.
Composite Expression
The term composite expression now supersedes the term complex expression.
The Standard Type System
ISO C99 Types
The ISO C99 Types language standard defines a range of types as depicted in the diagram shown below.
Page 83


---
*Page 83*

The discussion of essential type addressed in this document provides an alternative way of describing any expression of
arithmetic type. Arithmetic types and pointer types are two sub-classes of the set of "scalar" types. Every object, literal
constant and expression of arithmetic type has a type defined by the semantics of the C language.
We will refer to this type as the Standard Type to distinguish it from Essential Type - which will be described later.
Terminology
The ISO C99 document defines the following terms in section 6.2.5
Types
Description
Standard signed integer types
signed char, short int, int, long int, long long int
Extended signed integer types
Implementation defined
Signed integer types
Standard signed integer types and Extended signed integer types
Page 84


---
*Page 84*

Types
Description
Standard unsigned integer types
_Bool, unsigned char, unsigned short int, unsigned int, unsigned long int,
unsigned long long int
Extended unsigned integer types
Implementation defined
Unsigned integer types
Standard unsigned integer types and Extended unsigned integer types
Standard integer types
Signed integer types and Unsigned integer types
Real floating types
float, double, long double
Complex types
float _Complex, double _Complex, long double _Complex
Floating types
Real floating types and Complex types
Basic types
char, signed integer types, unsigned integer types and floating types
Character types
char, signed char, unsigned char
Enumeration
A set of named integer constant values
Enumerated type
An enumeration (each enumeration has a different enumerated type)
Integer types
char, signed integer types, unsigned integer types
Real types
Integer types and floating types
Arithmetic types
Integer types and floating types
Derived types
Array type, structure type, union type, function type
Pointer type
Derived from function type, object type or incomplete type called the reference
type
Scalar types
Arithmetic types and pointer types
Aggregate types
Array and structure types
Incomplete type
Array of unknown size, structure or union of unknown content
Derived declarator types
Array types, function types and pointer types
Rank
The family of standard signed and unsigned types and type char form a hierarchy which is described by the term "rank".
Signed and unsigned long long share the highest rank. _Bool has the lowest rank. The three character types signed char,
unsigned char and "plain" char are all of the same rank.
In the ISO-C standard, "rank" is a term applied only to integral types. In this discussion we shall extend the concept to
floating types thus:
Page 85


---
*Page 85*

No two floating types shall have the same rank, even if they have the same representation.
The rank of long double shall be greater than the rank of double, which shall be greater than the rank of float.
Anomalies
The C language as defined in the ISO-C standard contains a number of weaknesses and inconsistencies in its definition
of arithmetic types. The effect of this is that the standard type of an expression is not always fully descriptive of the
essential nature of the data being represented. For example:
 n Integral Promotion - The set of integer types do not behave in a consistent way. As a result of integral
promotion, an expression which is intrinsically unsigned (for example "unsigned char + unsigned char") typically
has a standard type which is signed int.
 n Integer Constants -Integer constants only exist for the larger numeric types, that is [signed |unsigned] int, long
and long long types. There are no constants of type [signed |unsigned] short or [signed |unsigned] char (although
it is possible to define a constant expression of these types by using a cast).
 n Character Constants - The type of a character constant (for example ’x’) is defined to be int (not char).
 n Logical Expressions - A Boolean type does not exist in the C90 language. Type _Bool was introduced into C99,
but unfortunately, for reasons of backwards compatibility, the result of an equality (==, !=), relational (<, <=, >=, >)
or logical (&&, ||, !) operator is still of type signed int rather than type _Bool.
 n Bit-fields - There is no such thing as a bit-field type. Bit-fields are permitted by the language standard to be
defined with type int, signed int, unsigned int (and also _Bool in C99). This means, for example, that it is not
possible to cast to a bit-field type.
 n enum Variables - An enum variable has a type which is "implementation-defined". The implementation is free to
use any integer type which is capable of representing the enumeration. If the enumeration includes negative
values, the enum type will be a signed integer type. If the enumeration consists only of non-negative values, the
enum type may be either a signed or unsigned integer type.
 n enum Constants - Regardless of the type used to implement an enum variable, an enum constant is always of
type signed int.
Diagnostic Requirements
The C language imposes a very minimal set of constraints on the type of an expression which may be used in any
particular context. It is therefore quite possible to write perfectly legal code which, because of the type of an expression,
is either of questionable meaning or simply unsafe.
A few examples:
 n Operands of an Unlikely Type
 l Using an expression of Boolean type as an operand of a relational operator.
 l Using an expression of plain char type as an operand of a shift operator.
 n Unexpected Operand Combinations
 l Subtracting an expression of plain char type from an expression of signed or unsigned type.
 n Comparing an expression of plain char type with an expression of floating type.
 n Explicit Type Conversions
 l Casting an expression of Boolean type to a floating type.
 l Implicit Type Conversions which may Result in Loss of Precision or Value
Page 86


---
*Page 86*

 n Assigning an expression of floating type to an integer object.
 n Operations which result in the conversion of a signed expression (which could be negative) to an unsigned type.
 n Implicit Type Conversions which are ’questionable’
 l Assigning a non-enum value to an enum variable
 l Arithmetic expressions which mix signed/unsigned/character/Boolean/enum types in a way which violates
strong typing principles.
A fundamental problem encountered in identifying coding problems such as these is that, quite frequently, the type of an
expression as defined in the C language is inadequate or misleading in describing the essential characteristics of the
data which it represents. For example, it frequently happens that, because of integral promotion, an expression which is
intuitively and intrinsically unsigned is technically of type signed int according to the ISO C language standard. This is just
one of the anomalies in the C language described in the previous section which can give rise to much confusion.
Consider the following:
Example
extern void foo(int si, unsigned char uca, unsigned char ucb)
    {
           unsigned int ui;
        ui = si; /* A */
        ui = uca + ucb; /* B */
        ...
    }
Statement A: If the variable si contains a negative value, the result of the assignment in statement A will be
’implementation defined’ - and probably meaningless.
A static analysis tool will usually generate a diagnostic located on the assignment operation to point out the dangerous
type conversion from signed int to unsigned int. Implicit conversions from a signed type to an unsigned type are,
generally, dangerous.
Statement B: The implicit type conversion which takes place in the assignment operation is no different from that in
statement A because the type of the expression which results from adding two objects of type unsigned char is also
signed int.
However, most developers would consider statement B to be fundamentally different: the expression ’uca + ucb’ is
 ’essentially unsigned’ - it cannot have a negative value. However, in practice, the great majority of developers are quite
unaware of integral promotion and a diagnostic message which reported a "signed to unsigned" conversion would come
as an unwelcome surprise.
For this reason, a coding rule which simply bans "signed to unsigned" conversions is far too simplistic and a static
analysis tool which does not distinguish between "Statement A" and "Statement B" will inevitably generate messages
which are unhelpful and distracting.
Page 87


---
*Page 87*

Essential Type
In order to address subtle distinctions like those described above, the concept of essential type has been developed as a
way of describing more faithfully the essential nature of the data which is being represented in an arithmetic expression.
The essential type system provides a way of defining coding rules which are both intuitively sensible and unambiguous.
Essential Type Overview
Essential Type Category
The primary function of Essential Type is to provide an alternative type system which provides a more rational way of
describing the nature of any arithmetic expression.
To this end it is helpful to be able to refer to an arithmetic expression as having an essential type category. The
expression may then be described under one of the following headings:
 n essentially Boolean
 n essentially character
 n essentially enum
 n essentially signed
 n essentially unsigned
 n essentially floating
These six terms are used to distinguish the essential nature of the data represented by any expression of arithmetic type.
Essential Type
The essential type of an expression is denoted by one of the usual types:
Essential Type Category
Essential Types
boolean
_Bool
character
char
enum<i>
enum
signed
signed [char |short |int |long |long long]
unsigned
unsigned [char |short |int |long |long long]
floating
float, double or long double
Notice the following:
 n char is only used to describe data which is essentially character in nature.
 n signed char is only used to represent data which is essentially signed in nature.
 n unsigned char is only used to represent data which is . in nature.
Page 88


---
*Page 88*

 n Each enumeration is considered a unique type with a unique essential type category
 l referred to in this document using the notation enum<i> where i simply represents a unique reference by
which the enumeration is distinguished.
Essential Type Principles
Essential Type is a property of any expression having arithmetic type.
The Essential Type of an expression is often but not always the same as the Standard Type.
The Essential Type and Standard Type are only ever different where Standard Type is either signed int or unsigned int.
Where the Standard Type of an expression is signed int, the Essential Type may be either unsigned char, unsigned
short, signed char, signed short, signed int, char, _Bool or enum<i>.
Where the Standard Type of a non-constant expression is unsigned int, the Essential Type is either unsigned int or
another unsigned integer type which is implemented in the same size as an int.
Where the Standard Type of a constant expression is unsigned int, the Essential Type may be either unsigned int,
unsigned short or unsigned char.
Essential Type Definitions
As noted above, the Essential Type of many expressions is exactly the same as the Standard Type. In the following
paragraphs we refer only to the specific situations where Essential Type and Standard Type are different.
STLR and UTLR
The Essential Type of a constant expression which has an Standard Type of signed int and is essentially signed is
defined by determining the signed type of lowest rank which is capable of representing the actual value. This is referred
to as the STLR rule.
The UTLR rule (unsigned type of lowest rank) is similar but applies to constant expressions which have an Standard
Type of unsigned int and are essential
The Essential Type of a Bit-field
• BF1: The Essential Type of a bit-field which is implemented with an unsigned type is the unsigned type of lowest rank
which is able to represent the bit-field.
• BF2: The Essential Type of a bit-field which is implemented with a signed type is the signed type of lowest rank which is
able to represent the bit-field.
The Essential Type of a Literal Constant
The ISO-C99 standard defines the following constants of "integral type":
 n Integer constants
 n Enumeration constants
 n Character constants
Note:
Enumeration constants and character constants are of "integral type" but are not "integer constants".
Page 89


---
*Page 89*

Integer Constants
 n I1: If the Standard Type of an integer constant is "signed int", the Essential Type is the STLR.
 n I2: If the Standard Type of an integer constant is "unsigned int", the Essential Type is the UTLR.
enum Constants
The Standard Type of an enum constant in C is always int, regardless of the implemented type of the enumeration and
regardless of the type of any initializer expression used to define its value. For example, if an enum constant is initialised
with an unsigned value, say "500U", the constant will still be considered to have a Standard Type of signed int.
Two distinct types of enumeration need to be considered:
 i. An enumeration which defines an enumeration type. An enumeration defined in this way will be identified either
by a tag or a typedef or by being used directly in the definition of an object or function.
 enum ETAG {A, B, C};
 typedef enum {A, B, C} ETYPE;
 typedef enum ETAG {A, B, C} ETYPE;
 enum {A, B, C} x;
 ii. An enumeration which is used to define a set of constants (which may or may not be related). This will be referred
to as an anonymous enumeration. An enumeration defined in this way does not define a type because it is not
associated with any tag, typedef, object or function.
enum {A = 10, B = 20, C = 30};

 n E1: If an enumeration defines an enumeration type, the Essential Type of its enumeration constants is enum<i>.
 n E2:: If an enumeration is anonymous, the Essential Type of its enumeration constants is the STLR.
Character Constants
The Standard Type of a character constant (for example ’q’) is int - not type char.
Note:
In C++ character constants are of type char.
 n C1: The Essential Type of a character constant consisting of a single character is "char".
(However the Essential Type of a multiple character constant (’xy’) is the same as its Standard Type i.e. "int".)
Boolean Constants
The C99 standard provides no syntax to define a constant of explicitly _Bool type. The library header "stdbool.h" defines
"false" and "true" only in terms of constants 0 and 1 of type int. The only way to define a constant expression of type _
Bool explicitly is to use a cast, for example (_Bool)0 or (_Bool)1.
The Essential Type of an Arithmetic Expression
 1. Relational (< <= >= >), Equality (== !=) and Logical (&& ||!)
 n LOGIC: The Essential Type is _Bool.
Page 90


---
*Page 90*

 2. Shift (<< >>)
 n SHIFT1: If the LH operand is essentially signed or unsigned, the Essential Type of the result is the
Essential Type of the LH operand.
 3. Bitwise Complement (~)
 n COMP1: If the operand is essentially unsigned, the Essential Type of the result is the Essential Type of the
operand.
 4. Unary Plus (+)
 n PLUS: If the operand is essentially signed or unsigned, the Essential Type of the result is the same.
 5. Unary Minus (-)
 n MINUS1: If the operand is essentially signed and is a constant expression, the Essential Type of the result
is the STLR.
 n MINUS2: If the operand is essentially signed and the expression is non-constant, the Essential Type of the
result is the Essential Type of the operand.
 6. Conditional (? :)
 n COND1: If the Essential Type of the 2nd and 3rd operands is the same, the Essential Type of the result is
the same.
 n COND2: If the 2nd and 3rd operands are both essentially unsigned, the Essential Type of the result is the
Essential Type of highest rank.
 n COND3: If the 2nd and 3rd operands are both essentially signed, the Essential Type of the result is the
Essential Type of highest rank.
 n COND4: If one operand is an expression of essentially unsigned type and the other is a non-negative
constant expression of essentially signed type with an essential rank which is no greater than the essential
rank of the unsigned operand, the Essential Type of the result is the Essential Type of the unsigned
operand.
 7. Type Balancing Operations (* / % + - & |^)
 n BAL1: If both operands are essentially unsigned and both are constant expressions, the Essential Type of
the result is the UTLR.
 n BAL2: If both operands are essentially unsigned and either is non-constant, the Essential Type of the
result is the Essential Type of highest rank.
 n BAL3: If both operands are essentially signed and both are constant expressions, the Essential Type of
the result is the STLR.
 n BAL4: If both operands are essentially signed and either is non-constant, the Essential Type of the result
is the Essential Type of highest rank.
 n BAL5: If one operand is essentially unsigned and the other is a non-negative constant expression of
essentially signed type with an essential type rank which is no greater than the essential type rank of the
unsigned operand, the Essential Type of the result is the Essential Type of the unsigned operand.
 8. Multiply
Page 91


---
*Page 91*

 n MUL1: If one operand is essentially signed or essentially unsigned and the other is essentially Boolean,
the Essential Type of the result is Essential Type of the non-Boolean operand.
 9. Addition
 n ADD1: If one operand is essentially character and the other is essentially signed or unsigned with an
essential type which is no greater than int, the Essential Type of the result is char.
 10. Subtraction
 n SUB1: If the first operand is essentially character and the second is essentially signed or unsigned with an
essential type which is no greater than int, the Essential Type of the result is char.
 n SUB2: If both operands are essentially character constant expressions, the Essential Type of the result is
the STLR.
 11. Comma Operator
 n COMMA: The Essential Type is the Essential Type of the right hand operand.
Composite Expressions
Terminology
The term composite expression supersedes the term complex expression which was introduced in the MISRA C:2004
Guidelines document. Although the concepts remain similar, the definitions of the two terms are not identical.
The concept of a composite expression is used in order to define coding rules which consider it inadvisable for
consecutive arithmetic operations to be conducted in different types. For example:
ula = uca + ucb; /* Example 1 */
In this example an addition operation is followed by an assignment operation. The addition operation occurs (notionally)
in the essential type unsigned char; the result of the addition then undergoes an implicit widening conversion to unsigned
long for the purpose of assignment.
 ula = uca + ucb + ulc; /* Example 2 */
In this example two operands of type unsigned char (uca and ucb) are added and then the result is implicitly widened to
type unsigned long for addition to ulc.
In both cases, the subexpression "uca +ucb" is considered a composite expression. In the first example, the expression
is widened when assigned to "ula". In the second example, the expression is widened when added to to "ulc".
Composite Operators
The following operators are described as composite operators:
Types
Symbols
Multiplicative
* / %
Page 92


---
*Page 92*

Types
Symbols
Additive
+ -
Bitwise
& |^
Shift
<< >>
Conditional
?:
However, the conditional operator is only considered composite if either the 2nd or the 3rd operand is a composite
expression.
Composite Expressions
An expression is deemed to be "composite" if it is non-constant and its value is the result of a composite operator.
Essential Type Messages
Overview
Helix QAC for C generates a large number of messages to diagnose a wide range of conditions in source code. The
specification of a particular message is dictated in many instances by the need to support flexibility in meeting the
requirements of differing coding standards.
Within the complete library of  Helix QAC for C messages, there are many messages associated with ’type’ usage which
may be used to identify:
 n The type of an individual operand being used with a particular operator
 n The combination of particular types of operand in binary and ternary operations
 n Explicit type conversions which occur in a cast operation
 n Implicit type conversions which occur in a variety of contexts
The following sections of this document provide an overview of these messages. A key aspect throughout is that the
messages usually refer to the "essential type" and "essential type category" of an expression rather than the
"standard type" defined in the ISO C language standard. As discussed previously, in many situations the essential type
and standard type of an expression are identical; but in some contexts, the concept of essential type is useful in capturing
the essential nature of an expression in a way that is obscured by the standard C type system.
The -strictrank Option
When comparing types, some of the essential type messages use the terms "wider" and "narrower" when describing
the relationship between types. By default, the terms wider and narrower reflect the relationship between the
implemented sizes of the two types; therefore type long will only be wider than type int if the types are implemented in a
different number of bits.
If the strictrank option is applied, the behavior of such messages is altered and the terms wider and narrower no longer
reflect the relative implemented size but the relative rank of the two types. Therefore, if the strictrank option is applied,
type long is always considered to be wider than type int, even if both are implemented in the same number of bits.
The facility to apply this option provides a means of exposing situations where issues of portability may be significant.
Page 93


---
*Page 93*

Expression Type Usage Messages
The C language supports a wide range of operators but imposes very few restrictions on the way in which they may be
used. There are many situations where an expression of a particular type might be considered an inappropriate operand
for a specific operator. For example:
 n Performing a bitwise operation (&, |, ^, ~, <<, >>) on essentially signed data
 n Performing a logical operation on essentially floating data
 n Performing a relational operation (<, <=, >=, >) on essentially Boolean data
The tables below distinguish various kinds of expression, i.e. its essential type and whether or not it is a constant
expression. Each row in the table corresponds to an operator and one of its operands (i.e. operand 1, 2 or 3). The cells in
each table show the message number which may be used to highlight situations when the essential type of the operand
may be considered inappropriate to the context.
Page 94


---
*Page 94*


ESSENTIAL TYPE CATEGORY OF OPERAND
Operator
Operand
Boolean
character
enum non-const
expression
[]

4500
4510

Unary +
1
4501
4511
4521
Unary -
1
4501
4511
4521
+
1
4501

4521
+
2
4501

4521
-
1
4501

4521
-
2
4501

4521
*
1
4501
4511
4521
*
2
4501
4511
4521
/
1
4501
4511
4521
/
2
4501
4511
4521
%
1
4501
4511
4521
%
2
4501
4511
4521
~
1
4502
4512
4522
& |^
1
4502
4512
4522
& |^
2
4502
4512
4522
<<>>
1
4503
4513
4523
<<>>
2
4504
4514
4524
<<=>=>
1
4505


<<=>=>
2
4505


== !=
either



++ –
1
4507
4517
4527
!
1

4518
4528
Page 95


---
*Page 95*


ESSENTIAL TYPE CATEGORY OF OPERAND
Operator
Operand
Boolean
character
enum non-const
expression
&& ||
1

4518
4528
&& ||
2

4518
4528
?:
1

4519
4529
?:
2 and 3



Page 96


---
*Page 96*



ESSENTIAL TYPE CATEGORY OF OPERAND
Operator
Operand
enum const
expression
signed
non-const
expression
negative  signed
constant
expression
[]




Unary +
1



Unary -
1
4521


+
1
4521


+
2
4521


-
1
4521


-
2
4521


*
1
4521


*
2
4521


/
1
4521


/
2
4521


%
1
4521


%
2
4521


~
1
4522
4532
4532
& |^
1
4522
4532
4532
& |^
2
4522
4532
4532
<<>>
1
4522
4532
4532
<<>>
2
4524
4524
4534
<<=>=>
1



<<=>=>
2



== !=
either



++ –
1
constraint

constraint
Page 97


---
*Page 97*



ESSENTIAL TYPE CATEGORY OF OPERAND
Operator
Operand
enum const
expression
signed
non-const
expression
negative  signed
constant
expression
!
1
4528
4538
4538
&& ||
1
4528
4538
4538
&& ||
2
4528
4538
4538
?:
1
4529
4539
4539
?:
2 and 3



Page 98


---
*Page 98*



ESSENTIAL TYPE CATEGORY OF OPERAND
Operator
Operand
non-negative
signed constant
expression
unsigned
floating
[]



constraint
Unary +
1



Unary -
1



+
1



+
2



-
1



-
2



*
1



*
2



/
1



/
2



%
1


constraint
%
2


constraint
~
1
4542

constraint
& |^
1
4542

constraint
& |^
2
4542

constraint
<<>>
1
4542

constraint
<<>>
2
4544

constraint
<<=>=>
1



<<=>=>
2



== !=
either



++ –
1
constraint


Page 99


---
*Page 99*



ESSENTIAL TYPE CATEGORY OF OPERAND
Operator
Operand
non-negative
signed constant
expression
unsigned
floating
!
1
4548
4558
4568
&& ||
1
4548
4558
4568
&& ||
2
4548
4558
4568
?:
1
4549
4559
4569
?:
2 and 3



Page 100


---
*Page 100*

ETC of Operand
Message Number
Message Text
Boolean
4500
An expression of ’essentially Boolean’
type (%1s) is being used as an array
subscript.V

4501
An expression of ’essentially Boolean’
type (%1s) is being used as the %2s
operand of this arithmetic operator
(%3s).

4502
An expression of ’essentially Boolean’
type (%1s) is being used as the %2s
operand of this bitwise operator (%3s).

4503
An expression of ’essentially Boolean’
type (%1s) is being used as the left-
hand operand of this shift operator
(%2s).

4504
An expression of ’essentially Boolean’
type (%1s) is being used as the right-
hand operand of this shift operator
(%2s).

4505
An expression of ’essentially Boolean’
type (%1s) is being used as the %2s
operand of this relational operator
(%3s).

4507
An expression of ’essentially Boolean’
type (%1s) is being used as the operand
of this increment/ decrement operator
(%2s).
character
4510
An expression of ’essentially character’
type (%1s) is being used as an array
subscript.

4511
An expression of ’essentially character’
type (%1s) is being used as the %2s
operand of this arithmetic operator
(%3s).

4512
An expression of ’essentially character’
type (%1s) is being used as the %2s
operand of this bitwise operator (%3s).
Page 101


---
*Page 101*

ETC of Operand
Message Number
Message Text

4513
An expression of ’essentially character’
type (%1s) is being used as the left-
hand operand of this shift operator
(%2s).

4514
An expression of ’essentially character’
type (%1s) is being used as the right-
hand operand of this shift operator
(%2s).

4517
An expression of ’essentially character’
type (%1s) is being used as the operand
of this increment/ decrement operator
(%2s).

4518
An expression of ’essentially character’
type (%1s) is being used as the %2s
operand of this logical operator (%3s).

4519
An expression of ’essentially character’
type (%1s) is being used as the first
operand of this conditional operator
(%2s).
enum
4521
An expression of ’essentially enum’ type
(%1s) is being used as the %2s operand
of this arithmetic operator (%3s).

4522
An expression of ’essentially enum’ type
(%1s) is being used as the %2s operand
of this bitwise operator (%3s).

4523
An expression of ’essentially enum’ type
(%1s) is being used as the left-hand
operand of this shift operator (%2s).

4524
An expression of ’essentially enum’ type
(%1s) is being used as the right-hand
operand of this shift operator (%2s).

4527
An expression of ’essentially enum’ type
is being used as the operand of this
increment/decrement operator.
Page 102


---
*Page 102*

ETC of Operand
Message Number
Message Text

4528
An expression of ’essentially enum’ type
(%1s) is being used as the %2s operand
of this logical operator (%3s).

4529
An expression of ’essentially enum’ type
(%1s) is being used as the first operand
of this conditional operator (%2s).
signed
4532
An expression of ’essentially signed’
type (%1s) is being used as the %2s
operand of this bitwise operator (%3s).

4533
An expression of ’essentially signed’
type (%1s) is being used as the left-
hand operand of this shift operator
(%2s).

4534
An expression of ’essentially signed’
type (%1s) is being used as the right-
hand operand of this shift operator
(%2s).

4538
An expression of ’essentially signed’
type (%1s) is being used as the %2s
operand of this logical operator (%3s).

4539
An expression of ’essentially signed’
type (%1s) is being used as the first
operand of this conditional operator
(%2s).

4542
A non-negative constant expression of
’essentially signed’ type (%1s) is being
used as the %2s operand of this bitwise
operator (%3s).

4543
A non-negative constant expression of
’essentially signed’ type (%1s) is being
used as the left-hand operand of this
shift operator (%2s).

4544
A non-negative constant expression of
’essentially signed’ type (%1s) is being
used as the right-hand operand of this
shift operator (%2s).
Page 103


---
*Page 103*

ETC of Operand
Message Number
Message Text

4548
A non-negative constant expression of
’essentially signed’ type (%1s) is being
used as the %2s operand of this logical
operator (%3s).

4549
A non-negative constant expression of
’essentially signed’ type (%1s) is being
used as the first operand of this
conditional operator (%2s).
unsigned
4558
An expression of ’essentially unsigned’
type (%1s) is being used as the %2s
operand of this logical operator (%3s).

4559
An expression of ’essentially unsigned’
type (%1s) is being used as the first
operand of this conditional operator
(%2s).
floating
4568
An expression of ’essentially floating’
type (%1s) is being used as the %2s
operand of this logical operator (%3s).

4569
An expression of ’essentially floating’
type (%1s) is being used as the first
operand of this conditional operator
(%2s).
Assigning Type Conversion Messages
The term "assigning type conversion" is used to describe the implicit type conversion which occurs in a number of
situations in the C language where the value of an expression is converted to a different type.
For example:
 n A simple assignment operation (=). The value of the expression is implicitly converted to the type of the object to
which the expression is being assigned.
 n A compound assignment operation (*=, /=, +=, -=, <<=, >>=, &=, ^=, |=). These operations are equivalent to 2
operations of which the second is a simple assignment.
 n The initialization of an arithmetic object at its point of definition.
 n The assignment of a function argument to a function parameter in a function call.
 n The assignment of the value of a return expression to the type of the notional object represented by the function
return type.
All these operations share the common characteristic that the value of an expression may have to undergo an implicit
conversion to another type ’as if by assignment’ (a term used in the C language standard).
The precise message will depend on the following features of the expression being assigned:
Page 104


---
*Page 104*

 1. The essential type of the expression
 2. The standard type of the object to which the expression is being assigned.
 3. Whether the expression is
 a. a constant - i.e. a floating constant or an integer constant of some form
 b. a constant expression
 c. a non-constant expression - any other type of expression
 4. Whether the expression is a composite expression
 5. The context in which the type conversion occurs - initialisation, assignment, function argument, function return.
Assigning a Constant
Standard Type Of
Object
Essential Type Category of Constant
Boolean
character
enum<1>
enum<2>
signed
unsigned
floating
_Bool

4410
4420
4420
1294
1295
1266




1257
1257

char
4401

4421
4421
1292
1293
1266




1257
1257

enum<1>
4402
4412

4422
1295
1297
1266




1257
1257

enum<2>
4402
4412
4422

1295
1297
1266




1257
1257

signed
4403
4413
4423
4423
1256
1291
1266




1257
1256






1257

unsigned
4404
4414
4424
4424
1290
1256
1266




1256
1257





1257


floating
4405
4415
4425
4425
1298
1299
1264






1265
Page 105


---
*Page 105*

Assigning a Constant Expression
Standard Type Of
Object
Essential Type Category of Constant Expression
Boolean
character
enum<1>
enum<2>
signed
unsigned
floating
_Bool

4410
4420
4420
4430
4440
4450
char
4401

4421
4421
4431
4441
4451
enum<1>
4402
4412

4422
4432
4442
4452
enum<2>
4402
4412
4422

4432
4442
4452
signed
4403
4413
4423
4423
4463
4447
4453
unsigned
4404
4414
4424
4424
4436
4464
4454
floating
4405
4415
4425
4425
4437
4445
4465
Assigning a Non-Constant Expression
Standard Type Of
Object
Essential Type Category of Non-Constant Expression
Boolean
character
enum<1>
enum<2>
signed
unsigned
floating
_Bool

4410
4420
4420
4430
4440
4450
char
4401

4421
4421
4431
4441
4451
enum<1>
4402
4412

4422
4432
4442
4452
enum<2>
4402
4412
4422

4432
4442
4452
signed
4403
4413
4423
4423
4460
4443
4453




4470
4446





4480






4490


unsigned
4404
4414
4424
4424
4434
4461






4471
4454





4481






4491

Page 106


---
*Page 106*

Standard Type Of
Object
Essential Type Category of Non-Constant Expression
Boolean
character
enum<1>
enum<2>
signed
unsigned
floating
floating
4405
4415
4425
4425
4435
4445
4462






4472






4482






4492
Assigning Messages
ETC of Assigned Expression
Message Number
Message Text
Boolean
4400
N/A

4401
An expression of ’essentially Boolean’
type (%1s) is being converted to
character type

4402
An expression of ’essentially Boolean’
type (%1s) is being converted to enum
type

4403
An expression of ’essentially Boolean’
type (%1s) is being converted to signed
type

4404
An expression of ’essentially Boolean’
type (%1s) is being converted to
unsigned type

4405
An expression of ’essentially Boolean’
type (%1s) is being converted to floating
type
character
4410
An expression of ’essentially character’
type (%1s) is being converted to
Boolean type, ’%2s’ on assignment.

4411
N/A

4412
An expression of ’essentially character’
type (%1s) is being converted to enum
type, ’%2s’ on assignment.
Page 107


---
*Page 107*

ETC of Assigned Expression
Message Number
Message Text

4413
An expression of ’essentially character’
type (%1s) is being converted to signed
type, ’%2s’ on assignment.

4414
An expression of ’essentially character’
type (%1s) is being converted to
unsigned type, ’%2s’ on assignment.

4415
An expression of ’essentially character’
type (%1s) is being converted to floating
type, ’%2s’ on assignment.
enum
4520
An expression of ’essentially enum’ type
(%1s) is being converted to Boolean
type

4521
An expression of ’essentially enum’ type
(%1s) is being converted to character
type

4422
An expression of ’essentially enum’ type
(%1s) is being converted to a different
enum type

4423
An expression of ’essentially enum’ type
(%1s) is being converted to signed type

4424
An expression of ’essentially enum’ type
(%1s) is being converted to unsigned
type

4425
An expression of ’essentially enum’ type
(%1s) is being converted to floating type
signed
4430
An expression of ’essentially signed’
type (%1s) is being used as the %2s
operand of this bitwise operator (%3s).

4431
An expression of ’essentially signed’
type (%1s) is being converted to
character type, ’%2s’ on assignment.

4432
An expression of ’essentially signed’
type (%1s) is being converted to enum
type, ’%2s’ on assignment.

4433
N/A
Page 108


---
*Page 108*

ETC of Assigned Expression
Message Number
Message Text

4434
A non-constant expression of
’essentially signed’ type (%1s) is being
converted to unsigned type, ’%2s’ on
assignment.

4435
A non-constant expression of
’essentially signed’ type (%1s) is being
converted to floating type, ’%2s’ on
assignment.

4436
A constant expression of ’essentially
signed’ type (%1s) is being converted to
unsigned type, ’%2s’ on assignment.

4437
A constant expression of ’essentially
signed’ type (%1s) is being converted to
floating type, ’%2s’ on assignment.

4460
A non-constant expression of
’essentially signed’ type (%1s) is being
converted to narrower signed type,
’%2s’ on assignment.

4463
A constant expression of ’essentially
signed’ type (%1s) is being converted to
narrower signed type, ’%2s’ on
assignment.

4480
A non-constant expression of
’essentially signed’ type (%1s) is being
returned from a function defined with a
wider signed return type, ’%2s’.

1290
An integer constant of ’essentially
signed’ type is being converted to
unsigned type on assignment.

1292
An integer constant of ’essentially
signed’ type is being converted to type
char on assignment.

1294
An integer constant of ’essentially
signed’ type is being converted to type _
Bool on assignment.
Page 109


---
*Page 109*

ETC of Assigned Expression
Message Number
Message Text

1296
An integer constant of ’essentially
signed’ type is being converted to enum
type on assignment.

1298
An integer constant of ’essentially
signed’ type is being converted to
floating type on assignment.

1256
An integer constant suffixed with L is
being converted to type signed or
unsigned long long on assignment.

1257
An integer constant suffixed with L or LL
is being converted to a type of lower
rank on assignment.
unsigned
4440
An expression of ’essentially unsigned’
type (%1s) is being converted to
Boolean type, ’%2s’ on assignment.

4441
An expression of ’essentially unsigned’
type (%1s) is being converted to
character type, ’%2s’ on assignment.

4442
A non-constant expression of
’essentially unsigned’ type (%1s) is
being converted to a wider signed type,
’%2s’ on assignment.

4444
N/A

4445
An expression of ’essentially unsigned’
type (%1s) is being converted to floating
type, ’%2s’ on assignment.

4446
A non-constant expression of
’essentially unsigned’ type (%1s) is
being converted to signed type, ’%2s’ on
assignment.

4447
A constant expression of ’essentially
unsigned’ type (%1s) is being converted
to signed type, ’%2s’ on assignment.
Page 110


---
*Page 110*

ETC of Assigned Expression
Message Number
Message Text

4461
A non-constant expression of
’essentially unsigned’ type (%1s) is
being converted to narrower unsigned
type, ’%2s’ on assignment.

4464
A constant expression of ’essentially
unsigned’ type (%1s) is being converted
to narrower unsigned type, ’%2s’ on
assignment.

4471
A non-constant expression of
’essentially unsigned’ type (%1s) is
being passed to a function parameter of
wider unsigned type, ’%2s’.

4481
A non-constant expression of
’essentially unsigned’ type (%1s) is
being returned from a function defined
with a wider unsigned return type, ’%2s’.

1291
An integer constant of ’essentially
unsigned’ type is being converted to
signed type on assignment.

1293
An integer constant of ’essentially
unsigned’ type is being converted to
type char on assignment.

1295
An integer constant of ’essentially
unsigned’ type is being converted to
type _Bool on assignment.

1297
An integer constant of ’essentially
unsigned’ type is being converted to
enum type on assignment.

1299
An integer constant of ’essentially
unsigned’ type is being converted to
floating type on assignment.

1256
An integer constant suffixed with L is
being converted to type signed or
unsigned long long on assignment.
Page 111


---
*Page 111*

ETC of Assigned Expression
Message Number
Message Text

1257
An integer constant suffixed with L or LL
is being converted to a type of lower
rank on assignment.
floating
4450
An expression of ’essentially floating’
type (%1s) is being converted to
Boolean type ’%2s’ on assignment.

4451
An expression of ’essentially floating’
type (%1s) is being converted to
character type ’%2s’ on assignment.

4452
An expression of ’essentially floating’
type (%1s) is being converted to enum
type ’%2s’ on assignment.

4453
An expression of ’essentially floating’
type (%1s) is being converted to signed
type ’%2s’ on assignment.

4454
An expression of ’essentially floating’
type (%1s) is being converted to
unsigned type ’%2s’ on assignment.

4455
N/A

4462
A non-constant expression of
’essentially floating’ type (%1s) is being
converted to narrower floating type,
’%2s’ on assignment.

4465
A non-constant expression of
’essentially floating’ type (%1s) is being
converted to narrower floating type,
’%2s’ on assignment.

4472
A non-constant expression of
’essentially floating’ type (%1s) is being
passed to a function parameter of wider
floating type, ’%2s’.

4482
A non-constant expression of
’essentially floating’ type (%1s) is being
returned from a function defined with a
wider floating return type, ’%2s’.
Page 112


---
*Page 112*

ETC of Assigned Expression
Message Number
Message Text

1264
A suffixed floating constant is being
converted to a different floating type on
assignment.

1265
An unsuffixed floating constant is being
converted to a different floating type on
assignment.

1266
A floating constant is being converted to
integral type on assignment.
Balancing Type Conversion Messages
The term "type balancing" describes what happens when 2 operands of different arithmetic type undergo implicit
conversion to a common type in the context of certain operators. This process is referred to in the ISO C language
standard as the "usual arithmetic conversions". The operators where type balancing occurs are:
Types
Symbols
Arithmetic
+ - * / %
Bitwise
& |^
Relational
<<=>=>
Conditional
?: (2nd and 3rd operands)
These messages may be used to identify situations where dangerous or inappropriate type balancing occurs between
operands of different essential type.
Note:
Other contexts where the type of an individual operand is inappropriate (regardless of the type of other
operands), are identified in a previous section.
Integer  / Float Conversions


Boolean
character
enum
signed
unsigned
floating
_Bool






char






enum





x
signed





x
Page 113


---
*Page 113*


Boolean
character
enum
signed
unsigned
floating
unsigned





x
floating


x
x
x

The following messages are generated when an expression of essentially enum, essentially signed or essentially
unsigned type is balanced with an operand of essentially floating type.
Message Number
Message Text
1800
The %1s operand (essential type: ’%2s’) will be implicitly converted to a floating type, ’%3s’, in this
arithmetic operation.
1801
The %1s operand (essential type: ’%2s’) will be implicitly converted to a floating type, ’%3s’, in this
bitwise operation.
1802
The %1s operand (essential type: ’%2s’) will be implicitly converted to a floating type, ’%3s’, in this
relational operation.
1803
The %1s operand (essential type: ’%2s’) will be implicitly converted to a floating type, ’%3s’, in this
equality operation.
1804
The %1s operand (essential type: ’%2s’) will be implicitly converted to a floating type, ’%3s’, in this
conditional operation.
Signed / Unsigned Conversions

Boolean
character
enum
signed
unsigned
floating
_Bool






char






enum






signed



x
x

unsigned



x
x

floating






An extensive set of messages is associated with the situation when expressions of essentially signed and essentially
unsigned type are balanced. The messages distinguish five subtly different variations in the way that these type
conversions may be described:
 A. The essentially signed operand is non-constant and is converted to an unsigned type.
 B. The essentially signed operand is a constant expression of negative value and is converted to an unsigned type.
Page 114


---
*Page 114*

 C. The essentially signed operand is a constant expression of non-negative value and is converted to an unsigned
type.
 D. The essentially unsigned operand is implicitly converted to the essential type of the signed operand.
 E. The essential types of the two operands are both of lower rank than int. The result is of type signed int because of
integral promotion.
The signed/unsigned messages are further extended by generating a different message for each of the 5 classes of
operator, i.e.
 1. Arithmetic
 2. Bitwise
 3. Relational
 4. Equality
 5. Conditional

Message Number
Message Text
A
1
1820
The %1s operand is non-constant and ’essentially signed’ (%2s) but will be
implicitly converted to an unsigned type (%3s) in this arithmetic operation.
A
2
1821
The %1s operand is non-constant and ’essentially signed’ (%2s) but will be
implicitly converted to an unsigned type (%3s) in this bitwise operation.
A
3
1822
The %1s operand is non-constant and ’essentially signed’ (%2s) but will be
implicitly converted to an unsigned type (%3s) in this relational operation.
A
4
1823
The %1s operand is non-constant and ’essentially signed’ (%2s) but will be
implicitly converted to an unsigned type (%3s) in this equality operation.
A
5
1824
The %1s operand is non-constant and ’essentially signed’ (%2s) but will be
implicitly converted to an unsigned type (%3s) in this conditional operation.
B
1
1830
The %1s operand is constant, ’essentially signed’ (%2s) and negative but will
be implicitly converted to an unsigned type (%3s) in this arithmetic operation.
B
2
1831
The %1s operand is constant, ’essentially signed’ (%2s) and negative but will
be implicitly converted to an unsigned type (%3s) in this bitwise operation.
B
3
1832
The %1s operand is constant, ’essentially signed’ (%2s) and negative but will
be implicitly converted to an unsigned type (%3s) in this relational operation.
B
4
1833
The %1s operand is constant, ’essentially signed’ (%2s) and negative but will
be implicitly converted to an unsigned type (%3s) in this equality operation.
B
5
1834
The %1s operand is constant, ’essentially signed’ (%2s) and negative but will
be implicitly converted to an unsigned type (%3s) in this conditional operation.
Page 115


---
*Page 115*


Message Number
Message Text
C
1
1840
The %1s operand is constant, ’essentially signed’ (%2s) and non-negative but
will be implicitly converted to an unsigned type (%3s) in this arithmetic
operation.
C
2
1841
The %1s operand is constant, ’essentially signed’ (%2s) and non-negative but
will be implicitly converted to an unsigned type (%3s) in this bitwise operation.
C
3
1842
The %1s operand is constant, ’essentially signed’ (%2s) and non-negative but
will be implicitly converted to an unsigned type (%3s) in this relational
operation.
C
4
1843
The %1s operand is constant, ’essentially signed’ (%2s) and non-negative but
will be implicitly converted to an unsigned type (%3s) in this equality operation.
C
5
1844
The %1s operand is constant, ’essentially signed’ (%2s) and non-negative but
will be implicitly converted to an unsigned type (%3s) in this conditional
operation.
D
1
1850
The %1s operand is ’essentially unsigned’ (%2s) but will be implicitly converted
to a signed type (%3s) in this arithmetic operation.
D
2
1851
The %1s operand is ’essentially unsigned’ (%2s) but will be implicitly converted
to a signed type (%3s) in this bitwise operation.
D
3
1852
The %1s operand is ’essentially unsigned’ (%2s) but will be implicitly converted
to a signed type (%3s) in this relational operation.
D
4
1853
The %1s operand is ’essentially unsigned’ (%2s) but will be implicitly converted
to a signed type (%3s) in this equality operation.
D
5
1854
The %1s operand is ’essentially unsigned’ (%2s) but will be implicitly converted
to a signed type (%3s) in this conditional operation.
E
1
1860
The operands of this arithmetic operator are of different ’essential signedness’
but will generate a result of type ’signed int’.
E
2
1861
The operands of this bitwise operator are of different ’essential signedness’ but
will generate a result of type ’signed int’.
E
3
1862
The operands of this relational operator are of different ’essential signedness’
but will both be promoted to ’signed int’ for comparison.
E
4
1863
The operands of this equality operator are of different ’essential signedness’
but will both be promoted to ’signed int’ for comparison.
E
5
1864
The 2nd and 3rd operands of this conditional operator are of different ’essential
signedness’. The result will be in the promoted type ’signed int’.
Page 116


---
*Page 116*

Operands of Different ETC in a Relational Operation

Boolean
character
enum
signed
unsigned
floating
_Bool






char


x


x
enum

x
x
x
x

signed


x



unsigned


x



floating

x





Message Number
Message Text
1880
The operands of this relational operator are expressions of different ’essential type’ categories (%1s
and %2s).
Operands of Different ETC in an Equality or Conditional Operation

Boolean
character
enum
signed
unsigned
floating
_Bool

x
x
x
x
x
char
x

x


x
enum
x
x
x
x
x

signed
x

x



unsigned
x

x



floating
x
x





Message Number
Message Text
1881
The operands of this equality operator are expressions of different ’essential type’ categories (%1s
and %2s).
1882
The 2nd and 3rd operands of this conditional operator are expressions of different ’essential type’
categories (%1s and %2s).
Switch Case Type Conversion Messages
According to the ISO C99 language standard, section 6.8.4.2, when a switch statement is executed:
Page 117


---
*Page 117*

"The integer promotions are performed on the controlling expression. The constant expression in each
case label is converted to the promoted type of the controlling expression. If a converted value matches
that of the promoted controlling expression, control jumps to the statement following the matched case
label. Otherwise, if there is a default label, control jumps to the labeled statement. If no converted case
constant expression matches and there is no default label, no part of the switch body is executed."
Messages are generated on switch case labels when the essential type of the label is not consistent with the essential
type of the switch controlling expression.
ETC Of Case
Label
ETC of Switch Controlling Expression
Boolean
character
enum<1>
enum<2>
signed
unsigned
Boolean

570
570
570
570
570
character
570

570
570
570
570
enum<1>
570
570

570
570

enum<2>
570
570
570

v

signed
570
570
570
570
571
570




572

unsigned
570
570
570
570
570
571





572

Message Number
Message Text
570
This switch case label of ’essential type’ ’%1s’ is not consistent with a controlling expression of
essential type ’%2s’.
571
This switch case label of ’essential type’ ’%1s’ is not consistent with a controlling expression which
has an essential type of higher rank (%2s).
572
This switch case label of ’essential type’ ’%1s’ is not consistent with a controlling expression which
has an essential type of lower rank (%2s).
 n Message 570 is generated when
 l the essential type category of the switch case label differs from the essential type category of the switch
controlling expression, or
 l the case label and controlling expression are of different enum types.
Page 118


---
*Page 118*

 n Message 571 is generated when
 l the case label and controlling expression are both essentially signed or both essentially unsigned, and
 l the controlling expression is of type signed long long or unsigned long long, and
 l the case label is a constant suffixed with L or UL.
 n Message 572 is generated when
 l the case label and controlling expression are both essentially signed or both essentially unsigned, and
 l the essential type of the controlling expression is smaller than long, and
 l the case label is a constant suffixed with L, UL, LL or ULL.
Cast Operation Messages
According to the ISO C standard, casts may be used without restriction to convert the value of any expression of
arithmetic type to some specified arithmetic type. The freedom that the C language allows may sometimes conceal cast
operations which are of very doubtful meaning. For example:
 n Casting an expression of Boolean type to type char
 n Casting an expression of type char to type float
The following table displays a range of messages that may be displayed as a result of suspicious cast operations.
Standard
Type  of
Result
Essential Type Category of Operand

Boolean
character
enum<1>
enum<2>
signed
unsigned
Floating
Boolean

4310
4320
4320
4330
4340
4350
character
4301



4393
4394
4351
enum<1>
4302
4312

4322
4332
4342
4352
enum<2>
4302
4312
4322

4332
4342
4352
signed
4303



4390
4394
4395
unsigned
4304



4393
4391
4395
Floating
4305
4315
4325
4325
4393
4394
4392

ETC of Cast
Expression
Message Number
Message Text
Boolean
4301
An expression of ’essentially Boolean’ type (%1s) is being cast to
character type ’%2s’.

4302
An expression of ’essentially Boolean’ type (%1s) is being cast to enum
type, ’%2s’.
Page 119


---
*Page 119*

ETC of Cast
Expression
Message Number
Message Text

4303
An expression of ’essentially Boolean’ type (%1s) is being cast to signed
type, ’%2s’.

4304
An expression of ’essentially Boolean’ type (%1s) is being cast to
unsigned type, ’%2s’.

4305
An expression of ’essentially Boolean’ type (%1s) is being cast to floating
type, ’%2s’.
character
4310
An expression of ’essentially character’ type (%1s) is being cast to
Boolean type, ’%2s’.

4312
An expression of ’essentially character’ type (%1s) is being cast to enum
type, ’%2s’.

4315
An expression of ’essentially character’ type (%1s) is being cast to
floating type, ’%2s’.
enum
4320
An expression of ’essentially enum’ type (%1s) is being cast to Boolean
type, ’%2s’.

4322
An expression of ’essentially enum’ type (%1s) is being cast to type a
different enum type, ’%2s’.

4325
An expression of ’essentially enum’ type (%1s) is being cast to floating
type, ’%2s’.
signed
4330
An expression of ’essentially signed’ type (%1s) is being cast to Boolean
type ’%2s’.

4332
An expression of ’essentially signed’ type (%1s) is being cast to enum
type, ’%2s’.
unsigned
4340
An expression of ’essentially unsigned’ type (%1s) is being cast to
Boolean type ’%2s’.

4342
An expression of ’essentially unsigned’ type (%1s) is being cast to enum
type, ’%2s’.
floating
4350
An expression of ’essentially floating’ type (%1s) is being cast to Boolean
type ’%2s’.

4351
An expression of ’essentially floating’ type (%1s) is being cast to
character type ’%2s’.

4352
An expression of ’essentially floating’ type (%1s) is being cast to enum
type, ’%2s’.
Page 120


---
*Page 120*

Bitwise ~ and << Messages
MISRA C imposes some particular constraints on the way in which bitwise ~ and << may be used. Bitwise operations
such as ~ and << can generate high order bits in the promoted type of expressions. Problems arise when these
operators are used on an operand whose essential type is smaller than int.
Message Number
Message Text
4397
An expression which is the result of a ~or << operation has not been cast to its essential type.
4398
An expression which is the result of a ~or << operation has been cast to a different essential type
category.
4399
An expression which is the result of a ~or << operation has been cast to a wider type.
4498
An expression which is the result of a ~or << operation has been converted to a different essential
type category on assignment.
4499
An expression which is the result of a ~or << operation has been converted to a wider essential type
on assignment.
4570
The operand of this ~operator has an ’essential type’ which is narrower than type ’int’.
4571
The left-hand operand of this << operator has an ’essential type’ which is narrower than type ’int’.
These messages are generated by examining the context when a ~or << operation is encountered according to the
following algorithm:
if (essential type of operand is "narrower" than "int")
{
   if (result is the operand of a cast operator)
   {
           if the cast is to a different essential type category
           {
           Message 4398
           }
Page 121


---
*Page 121*

           else
           {
               if the cast is to a "wider" essential type
            {
            Message 4399
            }
           }
    }
    else if (result is used in an assigning operation)
    {
           if the assignment is to a different essential type category
           {
           Message 4498
           }
           else
           {
               if the assignment is to a "wider" essential type
               {
            Message 4499
               }
           }
    }
    else
    {
       Message 4397
       }
}
Page 122


---
*Page 122*

Composite Expression Messages
Helix QAC for C generates messages which identify when:
 a. The value of a composite expression is implicitly converted to a wider essential type in an assigning operation
 b. The value of a composite expression is used as one operand of an operator in which the usual arithmetic
conversions ("type balancing") are performed and the other operand is of wider essential type. Type balancing is
conducted in the following operations:
Types
Symbols
Multiplicative
* / %
Additive
+ -
Bitwise
& |^
Relational
<<=>=>
Equality
== !=
Conditional
?: (2nd and 3rd operands)
 c. The value of a composite expression is cast to a different essential type category.
 d. The value of a composite expression is cast to a wider essential type.
Message Number
Message Text
4490
A composite expression of ’essentially signed’ type (%1s) is being converted to wider signed
type, ’%2s’ on assignment.
4491
A composite expression of ’essentially unsigned’ type (%1s) is being converted to wider
unsigned type, ’%2s’ on assignment.
4492
A composite expression of ’essentially floating’ type (%1s) is being converted to wider floating
type, ’%2s’ on assignment.
1890
A composite expression of ’essentially signed’ type (%1s) is being implicitly converted to a
wider signed type, ’%2s’.
1891
A composite expression of ’essentially unsigned’ type (%1s) is being implicitly converted to a
wider unsigned type, ’%2s’.
1892
A composite expression of ’essentially floating’ type (%1s) is being implicitly converted to a
wider floating type, ’%2s’.
4393
A composite expression of ’essentially signed’ type (%1s) is being cast to a different type
category, ’%2s’.
Page 123


---
*Page 123*

Message Number
Message Text
4394
A composite expression of ’essentially unsigned’ type (%1s) is being cast to a different type
category, ’%2s’.
4395
A composite expression of ’essentially floating’ type (%1s) is being cast to a different type
category, ’%2s’.
4390
A composite expression of ’essentially signed’ type (%1s) is being cast to a wider signed type,
’%2s’.
4391
A composite expression of ’essentially unsigned’ type (%1s) is being cast to a wider unsigned
type, ’%2s’.
4392
A composite expression of ’essentially floating’ type (%1s) is being cast to a wider floating type,
’%2s’.
Page 124


---
*Page 124*
