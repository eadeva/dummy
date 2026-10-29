# 4 | Perl-Compatible Regular Expressions

4 | Perl-Compatible Regular Expressions
This section is a brief introduction to Perl-Compatible Regular Expressions; it is not an exhaustive tutorial. There are
many books and online resources for Perl-Compatible Regular Expressions (which we simply refer to as Regular
Expressions) and you are encouraged to look into these.
Online Resource: http://perldoc.perl.org/perlre.html
Matching Characters
Most of the Regular Expressions in a Naming Convention will specify a character, or range of characters to match, and
how many times to perform the match.
A literal character will match itself only. The period ’.’ matches any character. A range of characters is specified by
enclosing them in square brackets ’[’,’]’. For example [A-Z] will match any capital letter. If a selection of letters is
needed (rather than a range) then these should be enclosed in square brackets. For example, [AMz] will match A, M or
z only.
These can be concatenated so as to match sequences of letters. For example, [A-Z][a-z] will match any two
sequences of letters where the first is upper case and the second lower case.
Matching a Number of Times
The default is 1: that is, where no number of matches is specified, the pattern must match exactly once. Otherwise, the
following can be used to specify the number of times to match:
n An asterisk ’*’ matches zero or more.
n plus sign ’+’ matches one or more.
n A question mark ’?’ matches zero or one.
n Braces ’{’,’}’ are used to match a specific number of times or a range of times.
For example ’[A-Z][a-z]’ will match any word (including single letter ones) that starts with a capital followed by
lower case letters. So ’Speed’ and ’V’ both match, but ’velocity’ does not match.
’[AEIOU][a-z]+’ matches any 2 letter or longer word starting with a capital vowel followed by lower case letter(s). So
’Add’ ’An’ ’Egg’ all match, but ’A’ and ’open’ do not match.
There can be one or two numbers and a comma in the braces:
n One number means match that exact number of times, e.g. ’^[a-z]{6}$’ will match a string of six lower case
letters.
n Two numbers can specify a range to match, e.g. ’^[A-Z]{6,8}$’ means match a string of six, seven or eight
capital letters.
To match anything of a particular length, use the period ’.’ to match any character e.g.
’^.{1,31}$’ will match any strings between 1 and 31 characters.
Page 17


---
*Page 17*

Anchoring
It is important that Regular Expressions are matched against the entire identifier.
The following example should clarify this:
Suppose a rule states that member variables should start with m_. The pattern ’m_.’ seems suitable as it will match
both ’m_speed’ and ’m_size’.
However, it will also match ’sim_speed’. Indeed the pattern ’m_’ also matches this, as the pattern will match
anywhere within the identifier name.
To make sure that the expression matches the entire identifier, the start must be anchored with a caret ’^’ and the
end with a dollar ’$’. In this particular case, the end is not so important, as we are matching any character. However,
if we wanted all our member variables to end with an ’e’, the revised pattern ’^m_.e’ would still match m_speed as it
starts with ’m_’ and has zero or more characters followed by an ’e’. The correct pattern for this would be ’^m_.e$’, so
that there can be any number of any characters following the ’m_’, but there must be an ’e’ at the end.
Alternate Matching
Sometimes more than one pattern may be appropriate for a particular identifier.
For example, the naming of local variables in functions may follow some convention, but they may have exceptions
for loop variables such as ’i’. The Regular Expression can be constructed to match those identifiers that can be
ignored.
The pipe character ’|’ is used to separate two (or more) Regular Expressions. Matching of these is done in turn and
once a match is found, it is deemed true and checking will stop.
Using the above examples, the Regular Expressions are:
’ ^[ij]$|^b_’ - matches variables named i or j or beginning b_
Escaping Special Characters
Occasionally there may be a requirement to match characters that have a special meaning in a Regular Expression.
These special characters are ’^.[$()|*+?\’
For instance, the parenthesis may be needed in a type pattern, as this designates a function, or the open square bracket
may be needed in order to indicate that the type is an array. But in the Regular Expression, these characters will be
interpreted as having their special meaning. This means that the desired matching will not occur.
To overcome this, the special characters must be escaped with a backslash ’\’. However, the backslash itself needs to
be escaped.
So, to specify a left parenthesis in a Regular Expression, use ’\\(’ (that’s two backslashes and the parenthesis). To
specify a backslash, use ’\\\’ (three backslashes).
Page 18


---
*Page 18*

Configuration File Example
A simple example file is shown below along with a description for each rule:
#1 internal function identifier consists of words separated by _and with initial
letter capitalized
rule={'space':'OF','linkage':'I','pattern':'^([A-Z][a-z]*)(_[A-Z][a-z]*)*$',
'message':4800}
#2 block scope variables (except i and j) must start with b_
rule={'space':'OV','scope':'B','linkage':'N','pattern':'^[ij]$|^
(b_.*)$','message':4800}
#3 macros must be all capitals, underscores are allowed
rule={'space':'OM','pattern':'^[A-Z_]+$','message':4800} 
#4 all functions and variables must be 31 or less chars
rule={'space':'OF,OV','pattern':'^.{1,31}$','message':4800}
Getting Feedback on Errors
The error log is registered in NameCheckErrors.txt, which is written in the output directory. If a project has more than
one output directory, the same file will appear in each output directory corresponding to the source file on which the
check was run.
Configuration File
If the configuration file cannot be found, the log file will display the name of the file as given in the Project Properties.
Check that the correct filename has been given and that it has the correct access permissions set. If there are spaces in
the path, make sure that the entire filename is enclosed in quotes.
JSON Syntax Errors
All JSON error messages start with the line number of the configuration file that the error occurred on. Any syntax errors
in the JSON entries will be reported with the words ’Error: option parsing;’ followed by an explanation of the problem and
its location.
The value of ’invert’ is a Boolean value so must be either the literal text true or false. The value of ’message’ is a
number. Quotes must not be used for either of these values, as this would make them string values.
Unknown Name
This occurs when a Rule name other than those in section Rule Names is used.
These must all be lower case.
For example ’Scope’:’I’ will produce the following message:
Line 1 Unknown object member name 'Scope' with string value I
{'Scope':'I'}
Change the capital ’S’ to lower case to correct the error.
Page 19


---
*Page 19*

Unknown value
This happens when the value for an object is not one of the permissible options. Objects that take a Regular Expression
(filename, pattern, type) can never have this error.
For example, ’linkage’:’E’ will produce the following message:
Line 2 Unknown value 'E'
In this case, the intention is probably external linkage, which is denoted by ’X’, rather than ’E’.
Regular Expressions
The Regular Expressions for filename, pattern and type are compiled as the configuration file is processed. Any errors
that occurred will be reported.
For example:
Line 29 Pattern Regular expression '[[:ower:]]*' compile fail:
bad class at offset 3 {'pattern':'[[:ower:]]*'}
The offset shows the location of the problem in the Regular Expression. In some cases, such as mismatched
brackets, problems are reported at the end of the string.
Page 20


---
*Page 20*
