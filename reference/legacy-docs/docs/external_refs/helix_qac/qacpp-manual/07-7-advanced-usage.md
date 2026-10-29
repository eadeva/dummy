# 7 | Advanced Usage

7 | Advanced Usage
This section covers the advanced usage of Helix QAC for C++.
Code Replacement
Helix QAC for C++ allows for the search and replacement of source code using regular expressions. This functionality
can be used to:
n Work around unsupported compiler extensions.
n Automatically control message visibility for auto-generated code.
n Apply custom "non-intrusive" suppressions.
Code Replacement Configuration Option
Regular expressions are specified to the tool using the -coderegex,-cre configuration option:
-coderegex=’s/<regex>/<replacement>/<modifiers>’
Multiple options can be specified. The tool attempts to apply the specified replacements in the order in which they were
specified.
Once a matching regular expression has been found, it will be applied. Regular expressions are not recursive, that is,
replacement expressions will not be applied to the replacement text of a previous regular expression. For example:
-coderegex=’s/global/local/c’ -coderegex=’s/localvar/X/c’
// Parsed by tool as 'int localvar;' and not 'int X;' int globalvar;    
Non-ASCII characters:
Matching of regular expressions operates on single ’char’ characters only (ie. single bytes). Matching takes place after
the source has been transcoded to the tool’s internal representation, UTF-8.
Regular Expression Syntax
Replacement pairs are specified using the following standard notation:
s/search regular expression/replacement string/modifiers
Most common regular expression syntax is supported, including the use of matching subexpressions in the replacement
string. For example:
s/__property([ˆ=]*)=[ˆ;]*;/\1;/
// Parsed by tool as 'long Creator;'__property long Creator = {read = get_
Creator}; 
Page 83


---
*Page 83*

The matching of regular expression may span multiple lines1. For example, the same __property regular expression
will also match the following:
// Parsed by tools as:
// long Destroyer
//;
__property long Destroyer = {read = get_Creator};       
Modifiers and Padding
The regular expression modifiers allow control over the addition of lines and spaces to ensure that line and column
locations continue to match the original source code elsewhere in the file. The available modifiers are:
l: Do not pad replacement expression with newlines
c: Do not pad replacement expression with spaces
Unless the l modifier is included, the tool will attempt to keep the number of lines consistent by inserting newline
characters at the end of the replacement string.
Unless the c modifier is included, the tool will attempt to keep the column positions consistent by inserting space
characters at the end of the replacement string.
Information:
When the modifiers are used, or if the replacement string in the regular expression itself adds more lines
or columns than appear in the original source, then the line and column numbers seen by the tool will not
be in sync with the original source file. This will result in locations used for diagnostics and metrics
appearing to be unsynchronized with the original source file.
Layout Configuration Files
Helix QAC for C++ has an advanced layout checking engine that operates directly at the level of statements and
expressions. Layout rules are defined directly against real C++ grammar terms resulting in fine grained control over the
indentation, brace style, spacing, and line breaks of the source code.
Helix QAC for C++ ships several default layout configuration files:
n exdented.layout Checks that source code layout is consistent with the exdented scheme.
n exdented-spacing.layout Checks that source code layout is consistent with the exdented scheme and also
checks spacing.
n indented.layout Checks that source code layout is consistent with the indented scheme.
n indented-spacing.layout Checks that source code layout is consistent with the indented scheme and
also checks spacing.
n knr.layout Checks that source code layout is consistent with the knr scheme.
1The tool follows the standard convention that a ’.’ character does not match the newline character
Page 84


---
*Page 84*

n knr-spacing.layout Checks that source code layout is consistent with the knr scheme and also checks
spacing.
n nospacing.layout Template file without any indent or spacing checking.
The desired layout file can be selected using the -layoutfile,-lf option and can be found in the Helix QAC installation in the
config/lcf folder.
Layout rules consist of "decorations" that describe the relative position of C++ tokens. Helix QAC for C++ uses the
following decorations in layout rules:
/s(value)
a specific amount (value) of spacing is expected.
/n
a new line is expected.
/I(value)
a specific amount (value) of indentation is expected. The indentation is relative
to the current indentation level. For example, if you do not want the new line
indented any further, specify /i0. The width of indentation is determined by -
layoutindentwidth,-liw.
/c(value)
the column number in which text should start.
The above decorations are used to make up rules that look something like:
if-stmt = 'if' '(' /s1 expr /s1 ')' cmpd-stmt
This is a simple rule for if statements. It determines that an if statement should consist of if, an expression within brackets
’(’ expr ’)’, one space /s1 before and after the expression, and a compound statement cmpd-stmt. Helix QAC
for C++ will generate a warning if the if statements in your source code do not conform to this layout style. If you remove
the /s decorations, Helix QAC for C++ will not enforce spacing and any number of spaces may exist around the
expression.
It is recommended that you only modify the above layout decorations in the message rules and not the rule grammar
itself. An easy way to modify message rules is to search the layout files to find the layout rules for a specific construct and
use the layout decorations to define a layout style. For a list of layout configuration terms, see Layout Configuration
Glossary .
Modifying Spacing Rules
You can modify the above rule to enforce spacing within if statements by using the /s decoration. For example, the
following rule:
if-stmt = 'if' '(' /s0 expr /s0 ')' cmpd-stmt
will generate a warning if there is a space between the brackets and the expression (expr).
Adding Line Breaks
Line breaks are enforced by using the /n decoration. For example, the following rule:
if-stmt = 'if' '(' /s1 expr /s1 ')' /n/i0 cmpd-stmt
will generate a warning if the compound statement (cmpd-stmt) of an if statement is not located on a new line (/n) with
no indentation (/i0).
Whenever a rule includes a line break, the indentation decoration for the new line needs to be specified according to your
indentation style. Line breaks and indention are used when you are enforcing a brace style.
Page 85


---
*Page 85*

Decoration Alternatives
You can specify more than one layout condition by entering a combination of decoration alternatives. For example, the
following rule:
if-stmt = 'if' '(' (/s0|/s1) expr (/s0|/s1) ')' cmpd-stmt
will allow zero or one space ( /s0|/s1 ) between the brackets and the expression in if statements.
Assigning Messages to Layout Rules
If you are using a user message file, you may want to assign particular warning messages to different rules. This can be
done by creating a rule that references warning messages. For example:
if-stmt = 'if' '(' (/s0|/s1) $5001 expr (/s0|/s1) $5001 ')' cmpd-stmt
This rule would generate warning 5001 if there is more than one space between the brackets and the expression.
Using Layout to Enforce a Brace Style
The following rule is part of the exdented.layout file and uses bracing and line break decorations to enforce an exdented
brace style for class definitions.
class-def = 'class|struct|etc' name [ base-clause | ]
/n/i0 '{' [ dlay-stmt-block /n/i0 '}' | (/n/i0|/s) '}' ]
This rule expects a token such as class before a name, followed by an optional base class base-clause. Because
the brace style of this rule is exdented, the opening brace, {, appears on a new line without any indentation (/n/i0) with an
optional delay statement block (dlay-stmt-block). The class definition is closed with a new line and a closing brace ( /n/i0
’}’ ).
Note:
In the rule above, class|struct|etc is an arbitrary name for an expected token and is used only as a guide
to what might be expected by the parser.
The following code sample would be acceptable and would not result in a layout warning:
struct name
{
...
}
Using Layout to Enforce a Spacing Standard
Usually a layout standard will expect a specific amount of spacing between certain tokens of your code. A layout
configuration file can be used to enforce a specific amount of spacing through the addition of /s decorations. To do this,
search your layout file to locate the rule for which you want to add spacing. For a list of layout configuration terms, see
Layout Configuration Glossary.
For example, the following rule specifies the amount of spacing within a comma separated list of expressions:
Page 86


---
*Page 86*

expr-list = expr-list /s0 ',' /s1 expr
This rule will expect a comma without a space /s0 ’,’ to immediately follow an expression expr-list and a space
/s1 before the next expression expr.
By putting the first expression as an expression list, this rule will allow several expressions that are separated by a
comma and a space. For example, the following code sample would not generate a layout warning.
function(x+y, z);
Modeling of the assert macro
Helix QAC for C++ models the assert macro differently to other macros. Specifically, the replacement list of a
#define directive for assert will be ignored, with the following used in its place:
__qacpp_assert ( static_cast<bool>( macro_param ) )
#define assert(x) // Normally defines 'assert' to expand to nothing
void f () {
assert(sizeof(int) > sizeof(char));
// assert expands to:
// __qacpp_assert(static_cast<bool>(sizeof(int) > sizeof(char)))
}
The benefit of this modeling is that analysis relating to the assert macro has deterministic behavior1.
Another benefit is the use of this information to improve the signal to noise of dataflow analysis:
void foo (int * p) {
assert(p);
*p = 0; // No issue reported
}
In this example, dataflow analysis is aware through the use of assert that the pointer is not null when it is dereferenced
later.
Reverting to standard preprocessor behavior
It is sometimes the case that assert is configured to expand to nothing for production builds. A violation of an assert at
runtime will not be detected in such a build:
1For example use static_assert in preferences to assert where possible
Page 87


---
*Page 87*

void doSomething(char*);
int main (int argc, char * argv[]) {
assert (argc > 3);
doSomething (argv[3]); // No issue reported
}
In order to detect issues that could arise when the assertions are violated, the modeling of assert can be disabled using -
prodoption assert::no_override
// -po prodoption assert::no_override
#define assert(x)
void doSomething(char*);
int main (int argc, char * argv[]) {
assert (argc > 3);
doSomething (argv[3]); // Possible issue reported.
}
Where a project uses a mixture of assertions, some of which remain in the production build, enabling this and explicitly
specifying __qacpp_assert only for the macros that are always present should provide for the optimal level of noise
reduction without the runtime risk.
#ifndef PRECONDITION
# error "Always expect PRECONDITION to be set"
#else
# undef PRECONDITION
# define PRECONDITION(Y) __qacpp_assert(static_cast<bool>(Y))
#endif        
Page 88


---
*Page 88*
