# 8 | Advanced Usage

8 | Advanced Usage
This section covers the advanced usage of  Helix QAC for C.
Code Replacement
Helix QAC for C allows for the search and replacement of source code using regular expressions.
This functionality can be used to:
 n Work around unsupported compiler extensions.
 n Automatically control message visibility for auto-generated code.
 n Apply custom "non-intrusive" suppressions.
Code Replacement Configuration Option
Regular expressions are specified to the tool using the -coderegex configuration option:
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
Most common regular expression syntax is supported, including the use of matching sub-expressions in the replacement
string. For example:
 s/__property([ˆ=]*)=[ˆ;]*;/\1;/



 // Parsed by tool as 'long Creator;'__property long Creator = {read = get_Creator};
Page 126


---
*Page 126*

The matching of regular expression may span multiple lines1. For example, the same __property regular expression
will also match the following:
 // Parsed by tools as:
 // long Destroyer
 // ;
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
1The tool follows the standard convention that a ’.’ character does not match the newline character
Page 127


---
*Page 127*
