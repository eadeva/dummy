# A | Dataflow Messages

A | Dataflow Messages
Dataflow Messages
Message ID
Message Text
Analyzer
Dataflow
Arrays
2835
Constant: Non-null terminated string used in
a string function.
✅
2836
Definite: Non-null terminated string used in a
string function.
✅
2839
Possible: Non-null terminated string used in a
string function.
✅
2840
Constant: Dereference of an invalid pointer
value.
✅
✅
2841
Definite: Dereference of an invalid pointer
value.
✅
2842
Apparent: Dereference of an invalid pointer
value.
✅
2843
Suspicious: Dereference of an invalid pointer
value.
✅
2844
Possible: Dereference of an invalid pointer
value.
✅
2845
Constant: Maximum number of characters to
be read/written is larger than the target buffer
size.
✅
2846
Definite: Maximum number of characters to
be read/written is larger than the target buffer
size.
✅
2847
Apparent: Maximum number of characters to
be read/written is larger than the target buffer
size.
✅
2848
Suspicious: Maximum number of characters
to be read/written is larger than the target
buffer size.
✅
Page 128


---
*Page 128*

Message ID
Message Text
Analyzer
Dataflow
2849
Possible: Maximum number of characters to
be read/written is larger than the target buffer
size.
✅
2930
Constant: Computing an invalid pointer value.
✅
2931
Definite: Computing an invalid pointer value.
✅
2932
Apparent: Computing an invalid pointer
value.
✅
2933
Suspicious: Computing an invalid pointer
value.
✅
2934
Possible: Computing an invalid pointer value.
✅
2935
Constant: Dereference of an invalid char
pointer value.
✅
2936
Definite: Dereference of an invalid char
pointer value.
✅
2937
Apparent: Dereference of an invalid char
pointer value.
✅
2938
Suspicious: Dereference of an invalid char
pointer value.
✅
2939
Possible: Dereference of an invalid char
pointer value.
✅
2950
Constant: Negative value used in array
subscript or pointer arithmetic operation.
✅
2951
Definite: Negative value used in array
subscript or pointer arithmetic operation.
✅
2952
Apparent: Negative value used in array
subscript or pointer arithmetic operation.
✅
2953
Suspicious: Negative value used in array
subscript or pointer arithmetic operation.
✅
2954
Possible: Negative tainted value used in
array subscript or pointer arithmetic
operation.
✅
Page 129


---
*Page 129*

Message ID
Message Text
Analyzer
Dataflow
3546
Definite: Calling a path manipulation function
with insufficient string size.
✅
3547
Apparent: Calling a path manipulation
function with insufficient string size.
✅
3548
Suspicious: Calling a path manipulation
function with insufficient string size.
✅
3549
Possible: Calling a path manipulation function
with insufficient string size.
✅
Control flow
2870
Infinite loop construct with constant control
expression.
✅
2871
Infinite loop identified.
✅
2872
This loop, if entered, will never terminate.
✅
2877
This loop will never be executed more than
once.
✅
✅
2880
This code is unreachable.
✅
2881
The code in this 'default' clause is
unreachable.
✅
2882
This 'switch' statement will bypass the
initialization of local variables.
✅
2883
This 'goto' statement will always bypass the
initialization of local variables.
✅
2885
This function doesn't return to the caller
despite not being declared as non-returning.
✅
2886
This function returns to the caller despite
being declared as non-returning.
✅
2887
Function 'main' ends with an implicit 'return'
statement.
✅
2888
This function has been declared with a non-
void 'return' type but ends with an implicit
'return ;' statement.
✅
Page 130


---
*Page 130*

Message ID
Message Text
Analyzer
Dataflow
2889
This function has more than one 'return' path.
✅
3535
The result from the function call has been
checked for '%1s' but not for '%2s'.
✅
Conversion to floating point
2925
Constant: Precision loss when converting
integral value to floating-point type.
✅
2926
Definite: Precision loss when converting
integral value to floating-point type.
✅
Invariant operations
2740
This loop controlling expression is a constant
expression and its value is 'true'.
✅
2741
This 'if' controlling expression is a constant
expression and its value is 'true'.
✅
2742
This 'if' controlling expression is a constant
expression and its value is 'false'.
✅
2743
This 'do - while' loop controlling expression is
a constant expression and its value is 'false'.
The loop will only be executed once.
✅
✅
2744
This 'while' or 'for' loop controlling expression
is a constant expression and its value is
'false'. The loop will not be entered.
✅
2990
The value of this loop controlling expression
is always 'true'.
✅
✅
2991
The value of this 'if' controlling expression is
always 'true'.
✅
✅
2992
The value of this 'if' controlling expression is
always 'false'.
✅
✅
2993
The value of this 'do - while' loop controlling
expression is always 'false'. The loop will only
be executed once.
✅
✅
2994
The value of this 'while' or 'for' loop controlling
expression is always 'false'. The loop will not
be entered.
✅
✅
Page 131


---
*Page 131*

Message ID
Message Text
Analyzer
Dataflow
2995
The result of this logical operation is always
'true'.
✅
✅
2996
The result of this logical operation is always
'false'.
✅
✅
2997
The first operand of this conditional operator
is always 'true'.
✅
✅
2998
The first operand of this conditional operator
is always 'false'.
✅
✅
NULL pointers
2810
Constant: Dereference of NULL pointer.
✅
2811
Definite: Dereference of NULL pointer.
✅
2812
Apparent: Dereference of NULL pointer.
✅
2813
Suspicious: Dereference of NULL pointer.
✅
2814
Possible: Dereference of NULL pointer.
✅
2820
Constant: Arithmetic operation on NULL
pointer.
✅
2821
Definite: Arithmetic operation on NULL
pointer.
✅
2822
Apparent: Arithmetic operation on NULL
pointer.
✅
2823
Suspicious: Arithmetic operation on NULL
pointer.
✅
2824
Possible: Arithmetic operation on NULL
pointer.
✅
Overflow and wraparound
2671
Definite: The value being compared with
macro EOF does not originate from an EOF
returning function.
✅
2674
Possible: The value being compared with
macro EOF does not originate from an EOF
returning function.
✅
Page 132


---
*Page 132*

Message ID
Message Text
Analyzer
Dataflow
2676
Definite: The value originating from an EOF
returning function was modified before being
compared with macro EOF.
✅
2678
Suspicious: The value originating from an
EOF returning function was modified before
being compared with macro EOF.
✅
2796
Definite: Calling a standard library character
handling function with an invalid character
value.
✅
2797
Apparent: Calling a standard library character
handling function with an invalid character
value.
✅
2798
Suspicious: Calling a standard library
character handling function with an invalid
character value.
✅
2799
Possible: Calling a standard library character
handling function with an invalid character
value.
✅
2800
Constant: Overflow in signed arithmetic
operation.
✅
2801
Definite: Overflow in signed arithmetic
operation.
✅
2802
Apparent: Overflow in signed arithmetic
operation.
✅
2803
Suspicious: Overflow in signed arithmetic
operation.
✅
2804
Possible: Overflow in signed arithmetic
tainted operation.
✅
2806
Definite: Calling a standard library wide
character handling function with an invalid
character value.
✅
2807
Apparent: Calling a standard library wide
character handling function with an invalid
character value.
✅
Page 133


---
*Page 133*

Message ID
Message Text
Analyzer
Dataflow
2808
Suspicious: Calling a standard library wide
character handling function with an invalid
character value.
✅
2809
Possible: Calling a standard library wide
character handling function with an invalid
character value.
✅
2816
Definite: Calling a standard library character
input/output function with an invalid character
value.
✅
2817
Apparent: Calling a standard library character
input/output function with an invalid character
value.
✅
2818
Suspicious: Calling a standard library
character input/output function with an invalid
character value.
✅
2819
Possible: Calling a standard library character
input/output function with an invalid character
value.
✅
2830
Constant: Division by zero.
✅
2831
Definite: Division by zero.
✅
2832
Apparent: Division by zero.
✅
2833
Suspicious: Division by zero.
✅
2834
Possible: Division by zero.
✅
2910
Constant: Wraparound in unsigned arithmetic
operation.
✅
2911
Definite: Wraparound in unsigned arithmetic
operation.
✅
2912
Apparent: Wraparound in unsigned arithmetic
operation.
✅
2913
Suspicious: Wraparound in unsigned
arithmetic operation.
✅
2914
Possible: Wraparound in unsigned arithmetic
tainted operation.
✅
Page 134


---
*Page 134*

Message ID
Message Text
Analyzer
Dataflow
2956
Definite: Using object '%s' with tainted value.
✅
2959
Possible: Using object '%s' with tainted value.
✅
3541
Definite: Using a tainted variable in a loop
control expression.
✅
3542
Apparent: Using a tainted variable in a loop
control expression.
✅
3543
Suspicious: Using a tainted variable in a loop
control expression.
✅
3544
Possible: Using a tainted variable in a loop
control expression.
✅
3560
Constant: Detected infinite overflow in float.
✅
3561
Definite: Detected infinite overflow in float.
✅
3566
Definite: Using a tainted query string.
✅
3567
Apparent: Using a tainted query string.
✅
3568
Suspicious: Using a tainted query string.
✅
4781
Definite: Signal handler causes the value of
errno to be indeterminate.
✅
4782
Apparent: Signal handler causes the value of
errno to be indeterminate.
✅
4783
Suspicious: Signal handler causes the value
of errno to be indeterminate.
✅
4784
Possible: Signal handler causes the value of
errno to be indeterminate.
✅
4841
Definite: Passing a file position argument to
fsetpos() not obtained from fgetpos().
✅
4842
Apparent: Passing a file position argument to
fsetpos() not obtained from fgetpos().
✅
4843
Suspicious: Passing a file position argument
to fsetpos() not obtained from fgetpos().
✅
Page 135


---
*Page 135*

Message ID
Message Text
Analyzer
Dataflow
4844
Possible: Passing a file position argument to
fsetpos() not obtained from fgetpos().
✅
4846
Definite: Signal handler returns from a
computational exception.
✅
4847
Apparent: Signal handler returns from a
computational exception.
✅
4848
Suspicious: Signal handler returns from a
computational exception.
✅
4849
Possible: Signal handler returns from a
computational exception.
✅
4851
Definite: File access time-of-check time-of-
use race condition.
✅
4852
Apparent: File access time-of-check time-of-
use race condition.
✅
4853
Suspicious: File access time-of-check time-
of-use race condition.
✅
4856
Definite: Atexit handler does not return
normally.
✅
4857
Apparent: Atexit handler does not return
normally.
✅
4858
Suspicious: Atexit handler does not return
normally.
✅
4859
Possible: Atexit handler does not return
normally.
✅
4861
Definite: Using an array containing
indeterminate values after a call to fgets or
fgetws.
✅
4862
Apparent: Using an array containing
indeterminate values after a call to fgets or
fgetws.
✅
4863
Suspicious: Using an array containing
indeterminate values after a call to fgets or
fgetws.
✅
Page 136


---
*Page 136*

Message ID
Message Text
Analyzer
Dataflow
4864
Possible: Using an array containing
indeterminate values after a call to fgets or
fgetws.
✅
4886
Definite: Time-of-check time-of-use race
condition when checking for the existence of
a symbolic link.
✅
4887
Apparent: Time-of-check time-of-use race
condition when checking for the existence of
a symbolic link.
✅
4888
Suspicious: Time-of-check time-of-use race
condition when checking for the existence of
a symbolic link.
✅
4906
Definite: Data may not be correctly converted
between host and network byte order.
✅
4907
Apparent: Data may not be correctly
converted between host and network byte
order.
✅
4908
Suspicious: Data may not be correctly
converted between host and network byte
order.
✅
4916
Definite: Using a tainted variable as format
string.
✅
4917
Apparent: Using a tainted variable as format
string.
✅
4918
Suspicious: Using a tainted variable as
format string.
✅
4919
Possible: Using a tainted variable as format
string.
✅
4921
Definite: Using a tainted variable as a device
name when opening a device that could be a
file.
✅
4922
Apparent: Using a tainted variable as a
device name when opening a device that
could be a file.
✅
Page 137


---
*Page 137*

Message ID
Message Text
Analyzer
Dataflow
4923
Suspicious: Using a tainted variable as a
device name when opening a device that
could be a file.
✅
4924
Possible: Using a tainted variable as a device
name when opening a device that could be a
file.
✅
Pointers
2668
Subtraction of a pointer to an array and a
pointer to a non-array.
✅
2669
Comparison of a pointer to an array and a
pointer to a non-array.
✅
2761
Definite: Subtracting pointers that address
different objects.
✅
2762
Apparent: Subtracting pointers that address
different objects.
✅
2763
Suspicious: Subtracting pointers that address
different objects.
✅
2766
Definite: Subtracting pointers that address
different members of the same object.
✅
2767
Apparent: Subtracting pointers that address
different members of the same object.
✅
2768
Suspicious: Subtracting pointers that address
different members of the same object.
✅
2771
Definite: Comparing pointers that address
different objects.
✅
2772
Apparent: Comparing pointers that address
different objects.
✅
2773
Suspicious: Comparing pointers that address
different objects.
✅
2776
Definite: Copy between overlapping objects.
✅
2777
Apparent: Copy between overlapping
objects.
✅
Page 138


---
*Page 138*

Message ID
Message Text
Analyzer
Dataflow
2778
Suspicious: Copy between overlapping
objects.
✅
2781
Definite: Function argument has fewer
elements than the array dimension in the
parameter declaration for non-inlined call.
✅
2782
Apparent: Function argument has fewer
elements than the array dimension in the
parameter declaration for non-inlined call.
✅
2783
Suspicious: Function argument has fewer
elements than the array dimension in the
parameter declaration for non-inlined call.
✅
2784
Possible: Function argument has fewer
elements than the array dimension in the
parameter declaration for non-inlined call.
✅
2785
Constant: Null terminated string is being
passed as argument to Standard Library
function memcmp.
✅
2786
Definite: Null terminated string is being
passed as argument to Standard Library
function memcmp.
✅
2789
Possible: Null terminated string is being
passed as argument to Standard Library
function memcmp.
✅
2826
Definite: Use of an object after its lifetime has
ended.
✅
2827
Apparent: Use of an object after its lifetime
has ended.
✅
2828
Suspicious: Use of an object after its lifetime
has ended.
✅
2916
Definite: Storing the address of an object in a
pointer that has greater lifetime.
✅
2917
Apparent: Storing the address of an object in
a pointer that has greater lifetime.
✅
2918
Suspicious: Storing the address of an object
in a pointer that has greater lifetime.
✅
Page 139


---
*Page 139*

Message ID
Message Text
Analyzer
Dataflow
2919
Possible: Storing the address of an object in a
pointer that has greater lifetime.
✅
3516
Definite: Object should have automatic
storage.
✅
4726
Definite: Comparison of padding bits that are
not part of the object representation.
✅
4727
Apparent: Comparison of padding bits that
are not part of the object representation.
✅
4728
Suspicious: Comparison of padding bits that
are not part of the object representation.
✅
4729
Possible: Comparison of padding bits that are
not part of the object representation.
✅
4751
Definite: Modifying an object that is
referenced by the return value of a library
function.
✅
4752
Apparent: Modifying an object that is
referenced by the return value of a library
function.
✅
4753
Suspicious: Modifying an object that is
referenced by the return value of a library
function.
✅
4876
Definite: Permanent user rights drop success
is not checked.
✅
4877
Apparent: Permanent user rights drop
success is not checked.
✅
4878
Suspicious: Permanent user rights drop
success is not checked.
✅
4879
Possible: Permanent user rights drop
success is not checked.
✅
4880
Constant: Pointed to object has smaller size
than the size_t argument.
✅
4881
Definite: Pointed to object has smaller size
than the size_t argument.
✅
Page 140


---
*Page 140*

Message ID
Message Text
Analyzer
Dataflow
4882
Apparent: Pointed to object has smaller size
than the size_t argument.
✅
4883
Suspicious: Pointed to object has smaller
size than the size_t argument.
✅
4884
Possible: Pointed to object has smaller size
than the size_t argument.
✅
4911
Definite: Assuming that fgets or fgetws
returned a non empty string.
✅
4912
Apparent: Assuming that fgets or fgetws
returned a non empty string.
✅
4913
Suspicious: Assuming that fgets or fgetws
returned a non empty string.
✅
4914
Possible: Assuming that fgets or fgetws
returned a non empty string.
✅
4941
Definite: Passing a padded structure from a
trusted boundary to another domain.
✅
4942
Apparent: Passing a padded structure from a
trusted boundary to another domain.
✅
4943
Suspicious: Passing a padded structure from
a trusted boundary to another domain.
✅
4955
Constant: Adding/subtracting a scaled
integer to a pointer.
✅
4956
Definite: Adding/subtracting a scaled integer
to a pointer.
✅
4957
Apparent: Adding/subtracting a scaled
integer to a pointer.
✅
Dataflow recovery
2750
Internal dataflow problem. Dataflow analysis
continues with the next function. Please
inform Programming Research.
✅
✅
2751
This function is too complex. Dataflow
analysis continues with the next function.
✅
✅
Page 141


---
*Page 141*

Message ID
Message Text
Analyzer
Dataflow
2752
This '%1s' results in the function being too
complex. Dataflow analysis continues with
the next function.
✅
✅
2755
Analysis time of function '%1s' has exceeded
the configured maximum: '%2sms'.  Dataflow
analysis continues with the next function.
✅
✅
2756
Could not expand function call to '%1s' with
maximum '-po df::inter' value.
✅
2757
Could not analyze function '%1s'.
✅
✅
2758
Query has exceeded the configured
maximum: '%1sms'.  Dataflow analysis
continues with the next query.
✅
2759
ODR violation for definition of '%1s'. Dataflow
analysis continues with the next function.
✅
✅
4801
Analysis Trait '%1' has been disabled.
✅
4802
Analysis Trait '%1' has incorrect format: %2.
✅
Redundancy
2865
Constant: Using 0 as size parameter of a
function call.
✅
2866
Definite: Using 0 as size parameter of a
function call.
✅
2867
Apparent: Using 0 as size parameter of a
function call.
✅
2868
Suspicious: Using 0 as size parameter of a
function call.
✅
2869
Possible: Using 0 as size parameter of a
function call.
✅
2980
The value of this function parameter is never
used before being modified.
✅
2981
This initialization is redundant. The value of
this object is never used before being
modified.
✅
Page 142


---
*Page 142*

Message ID
Message Text
Analyzer
Dataflow
2982
This assignment is redundant. The value of
this object is never used before being
modified.
✅
2983
This assignment is redundant. The value of
this object is never subsequently used.
✅
2984
This operation is redundant. The value of the
result is always '%1s'.
✅
2985
This operation is redundant. The value of the
result is always that of the left-hand operand.
✅
2986
This operation is redundant. The value of the
result is always that of the right-hand
operand.
✅
2987
This function call produces no side effects
and is redundant.
✅
Resources
2681
Definite: Using an invalidated value '%s'
returned from a Standard Library function.
✅
2682
Apparent: Using an invalidated value '%s'
returned from a Standard Library function.
✅
2683
Suspicious: Using an invalidated value '%s'
returned from a Standard Library function.
✅
2686
Definite: Writing to a file opened for reading.
✅
2687
Apparent: Writing to a file opened for reading.
✅
2688
Suspicious: Writing to a file opened for
reading.
✅
2691
Definite: The same file will be open with write
access and another mode.
✅
2692
Apparent: The same file will be open with
write access and another mode.
✅
2693
Suspicious: The same file will be open with
write access and another mode.
✅
Page 143


---
*Page 143*

Message ID
Message Text
Analyzer
Dataflow
2696
Definite: Attempt to access a file which has
been closed.
✅
2697
Apparent: Attempt to access a file which has
been closed.
✅
2698
Suspicious: Attempt to access a file which
has been closed.
✅
2701
Definite: Opened file is not closed.
✅
2702
Apparent: Opened file is not closed.
✅
2703
Suspicious: Opened file is not closed.
✅
2706
Definite: Allocated memory is not deallocated
(owning pointer: %1s).
✅
2707
Apparent: Allocated memory is not
deallocated (owning pointer: %1s).
✅
2708
Suspicious: Allocated memory is not
deallocated (owning pointer: %1s).
✅
2711
Definite: Memory allocation and deallocation
mismatch (owning pointer: %1s).
✅
2712
Apparent: Memory allocation and
deallocation mismatch (owning pointer: %1s).
✅
2713
Suspicious: Memory allocation and
deallocation mismatch (owning pointer: %1s).
✅
2716
Definite: Memory deallocated multiple times
(owning pointer: %1s).
✅
2717
Apparent: Memory deallocated multiple times
(owning pointer: %1s).
✅
2718
Suspicious: Memory deallocated multiple
times (owning pointer: %1s).
✅
2719
Possible: Memory deallocated multiple times
(owning pointer: %1s).
✅
2721
Definite: Deallocation of non dynamic
memory (owning pointer: %1s).
✅
Page 144


---
*Page 144*

Message ID
Message Text
Analyzer
Dataflow
2722
Apparent: Deallocation of non dynamic
memory  (owning pointer: %1s).
✅
2723
Suspicious: Deallocation of non dynamic
memory  (owning pointer: %1s).
✅
2724
Possible: Deallocation of non dynamic
memory  (owning pointer: %1s).
✅
2726
Definite: Use of uninitialized resource.
✅
2727
Apparent: Use of uninitialized resource.
✅
2728
Suspicious: Use of uninitialized resource.
✅
2731
Definite: Use of destroyed resource.
✅
2732
Apparent: Use of destroyed resource.
✅
2733
Suspicious: Use of destroyed resource.
✅
2736
Definite: Created resource is not destroyed.
✅
2737
Apparent: Created resource is not destroyed.
✅
2738
Suspicious: Created resource is not
destroyed.
✅
2746
Definite: Use of uninitialized file handle.
✅
2747
Apparent: Use of uninitialized file handle.
✅
2748
Suspicious: Use of uninitialized file handle.
✅
3518
Unsequenced modification and access to the
same object.
✅
3556
Definite: Use of a hardcoded secret.
✅
3557
Apparent: Use of a hardcoded secret.
✅
3558
Suspicious: Use of a hardcoded secret.
✅
3571
Definite: Using a tainted string '%1s' in an
SQL command.
✅
3572
Apparent: Using a tainted string '%1s' in an
SQL command.
✅
Page 145


---
*Page 145*

Message ID
Message Text
Analyzer
Dataflow
3573
Suspicious: Using a tainted string '%1s' in an
SQL command.
✅
3574
Possible: Using a tainted string '%1s' in an
SQL command.
✅
4711
Definite: Alternating I/O operations on a file
stream found without an intervening
positioning call or EOF.
✅
4712
Apparent: Alternating I/O operations on a file
stream found without an intervening
positioning call or EOF.
✅
4713
Suspicious: Alternating I/O operations on a
file stream found without an intervening
positioning call or EOF.
✅
4716
Definite: Alternating I/O operations on a file
stream found without an intervening
positioning call.
✅
4717
Apparent: Alternating I/O operations on a file
stream found without an intervening
positioning call.
✅
4718
Suspicious: Alternating I/O operations on a
file stream found without an intervening
positioning call.
✅
4866
Definite: Memory is used after free (owning
pointer: %1s).
✅
4867
Apparent: Memory is used after free (owning
pointer: %1s).
✅
4868
Suspicious: Memory is used after free
(owning pointer: %1s).
✅
4869
Possible: Memory is used after free (owning
pointer: %1s).
✅
4871
Definite: Zero size has been passed to
realloc, malloc or calloc.
✅
4872
Apparent: Zero size has been passed to
realloc, malloc or calloc.
✅
Page 146


---
*Page 146*

Message ID
Message Text
Analyzer
Dataflow
4873
Suspicious: Zero size has been passed to
realloc, malloc or calloc.
✅
4874
Possible: Zero size has been passed to
realloc, malloc or calloc.
✅
4891
Definite: Revocation order was not observed
while relinquishing privileges.
✅
4892
Apparent: Revocation order was not
observed while relinquishing privileges.
✅
4893
Suspicious: Revocation order was not
observed while relinquishing privileges.
✅
4894
Possible: Revocation order was not observed
while relinquishing privileges.
✅
4895
Constant: Value does not correspond to any
of enumeration's enumerators.
✅
4896
Definite: Value does not correspond to any of
enumeration's enumerators.
✅
4897
Apparent: Value does not correspond to any
of enumeration's enumerators.
✅
4898
Suspicious: Value does not correspond to
any of enumeration's enumerators.
✅
4899
Possible: Value does not correspond to any
of enumeration's enumerators.
✅
4901
Definite: Invalid call to va_arg.
✅
4902
Apparent: Invalid call to va_arg.
✅
4903
Suspicious: Invalid call to va_arg.
✅
4904
Possible: Invalid call to va_arg.
✅
4991
Definite: Using an invalidated value '%s' of
the environment pointer passed as the third
argument to main.
✅
4992
Apparent: Using an invalidated value '%s' of
the environment pointer passed as the third
argument to main.
✅
Page 147


---
*Page 147*

Message ID
Message Text
Analyzer
Dataflow
4993
Suspicious: Using an invalidated value '%s' of
the environment pointer passed as the third
argument to main.
✅
Shift operations
2790
Constant: Right hand operand of shift
operator is negative or too large.
✅
2791
Definite: Right hand operand of shift operator
is negative or too large.
✅
2792
Apparent: Right hand operand of shift
operator is negative or too large.
✅
2793
Suspicious: Right hand operand of shift
operator is negative or too large.
✅
2794
Possible: Tainted right hand operand of shift
operator is negative or too large.
✅
2860
Constant: Implementation-defined value
resulting from left shift operation on
expression of signed type.
✅
2861
Definite: Implementation-defined value
resulting from left shift operation on
expression of signed type.
✅
2862
Apparent: Implementation-defined value
resulting from left shift operation on
expression of signed type.
✅
2863
Suspicious: Implementation-defined value
resulting from left shift operation on
expression of signed type.
✅
2864
Possible: Implementation-defined value
resulting from left shift operation on tainted
expression of signed type.
✅
2920
Constant: Left shift operation on expression
of unsigned type results in loss of high order
bits.
✅
2921
Definite: Left shift operation on expression of
unsigned type results in loss of high order
bits.
✅
Page 148


---
*Page 148*

Message ID
Message Text
Analyzer
Dataflow
2922
Apparent: Left shift operation on expression
of unsigned type results in loss of high order
bits.
✅
2923
Suspicious: Left shift operation on expression
of unsigned type results in loss of high order
bits.
✅
2924
Possible: Left shift operation on tainted
expression of unsigned type results in loss of
high order bits.
✅
Conversion to signed
2850
Constant: Implicit conversion to a signed
integer type of insufficient size.
✅
2851
Definite: Implicit conversion to a signed
integer type of insufficient size.
✅
2852
Apparent: Implicit conversion to a signed
integer type of insufficient size.
✅
2853
Suspicious: Implicit conversion to a signed
integer type of insufficient size.
✅
2854
Possible: Implicit conversion of a tainted
expression to a signed integer type of
insufficient size.
✅
2855
Constant: Casting to a signed integer type of
insufficient size.
✅
2856
Definite: Casting to a signed integer type of
insufficient size.
✅
2857
Apparent: Casting to a signed integer type of
insufficient size.
✅
2858
Suspicious: Casting to a signed integer type
of insufficient size.
✅
2859
Possible: Casting a tainted expression to a
signed integer type of insufficient size.
✅
2940
Constant: Result of implicit conversion is only
representable in a two's complement
implementation.
✅
Page 149


---
*Page 149*

Message ID
Message Text
Analyzer
Dataflow
2941
Definite: Result of implicit conversion is only
representable in a two's complement
implementation.
✅
2942
Apparent: Result of implicit conversion is only
representable in a two's complement
implementation.
✅
2943
Suspicious: Result of implicit conversion is
only representable in a two's complement
implementation.
✅
2944
Possible: Result of implicit conversion of a
tainted expression is only representable in a
two's complement implementation.
✅
2945
Constant: Result of cast is only representable
in a two's complement implementation.
✅
2946
Definite: Result of cast is only representable
in a two's complement implementation.
✅
2947
Apparent: Result of cast is only representable
in a two's complement implementation.
✅
2948
Suspicious: Result of cast is only
representable in a two's complement
implementation.
✅
2949
Possible: Result of cast of a tainted
expression is only representable in a two's
complement implementation.
✅
Serious Threading Issues
3536
This lock operation can fail but its return
status is ignored.
✅
3537
This timed lock operation is being applied to a
non-timed mutex.
✅
3550
Constant: Calling an external locking function
which will block.
✅
3551
Definite: Calling an external locking function
which will block.
✅
Page 150


---
*Page 150*

Message ID
Message Text
Analyzer
Dataflow
3552
Apparent: Calling an external locking function
which will block.
✅
3553
Suspicious: Calling an external locking
function which will block.
✅
3554
Possible: Calling an external locking function
which will block.
✅
4926
Definite: The lifetime of the variable passed to
the thread creation function is shorter than
the lifetime of the thread.
✅
4927
Apparent: The lifetime of the variable passed
to the thread creation function is shorter than
the lifetime of the thread.
✅
4928
Suspicious: The lifetime of the variable
passed to the thread creation function is
shorter than the lifetime of the thread.
✅
4931
Definite: Initialising a mutex which has
already been initialised
✅
4932
Apparent: Initialising a mutex which has
already been initialised
✅
4936
Definite: Using a mutex which has not been
initialised
✅
4937
Apparent: Using a mutex which has not been
initialised
✅
4946
Definite: Mutex is still locked at thread exit
✅
4947
Apparent: Mutex is still locked at thread exit
✅
4951
Definite: Beware of race conditions when
using fork and file descriptors.
✅
4952
Apparent: Beware of race conditions when
using fork and file descriptors.
✅
4961
Definite: Attempt to destroy a mutex which is
still locked
✅
4962
Apparent: Attempt to destroy a mutex which
is still locked
✅
Page 151


---
*Page 151*

Message ID
Message Text
Analyzer
Dataflow
4966
Definite: Performing a blocking action while
holding a POSIX lock.
✅
4967
Apparent: Performing a blocking action while
holding a POSIX lock.
✅
4971
Definite: Attempt to destroy a mutex which
has not been created by the current thread
✅
4972
Apparent: Attempt to destroy a mutex which
has not been created by the current thread
✅
4976
Definite: Call to a non-reentrant function
outside of a critical section.
✅
4977
Apparent: Call to a non-reentrant function
outside of a critical section.
✅
4981
Definite: Attempt to unlock a mutex which has
not been locked by the current thread
✅
4982
Apparent: Attempt to unlock a mutex which
has not been locked by the current thread
✅
4986
Definite: Attempt to lock a non-recursive
mutex which is already locked
✅
4987
Apparent: Attempt to lock a non-recursive
mutex which is already locked
✅
4995
Constant: Using an invalid thread identifier.
✅
4996
Definite: Using an invalid thread identifier.
✅
4997
Apparent: Using an invalid thread identifier.
✅
4998
Suspicious: Using an invalid thread identifier.
✅
Unset data
2961
Definite: Using value of uninitialized
automatic object '%s'.
✅
2962
Apparent: Using value of uninitialized
automatic object '%s'.
✅
2963
Suspicious: Using value of uninitialized
automatic object '%s'.
✅
Page 152


---
*Page 152*

Message ID
Message Text
Analyzer
Dataflow
2966
Definite: Some members of object '%s' are
uninitialized.
✅
2967
Apparent: Some members of object '%s' are
uninitialized.
✅
2968
Suspicious: Some members of object '%s'
are uninitialized.
✅
2971
Definite: Passing address of uninitialized
object '%s' to a function parameter declared
as a pointer to const.
✅
2972
Apparent: Passing address of uninitialized
object '%s' to a function parameter declared
as a pointer to const.
✅
2973
Suspicious: Passing address of uninitialized
object '%s' to a function parameter declared
as a pointer to const.
✅
2976
Definite: Passing address of partially
initialized object '%s' to a function parameter
declared as a pointer to const.
✅
2977
Apparent: Passing address of partially
initialized object '%s' to a function parameter
declared as a pointer to const.
✅
2978
Suspicious: Passing address of partially
initialized object '%s' to a function parameter
declared as a pointer to const.
✅
4836
Definite: The C Atomic object is accessed
before being initialised.
✅
4837
Apparent: The C Atomic object is accessed
before being initialised.
✅
4838
Suspicious: The C Atomic object is accessed
before being initialised.
✅
Conversion to unsigned
2890
Constant: Negative value implicitly converted
to an unsigned type.
✅
Page 153


---
*Page 153*

Message ID
Message Text
Analyzer
Dataflow
2891
Definite: Negative value implicitly converted
to an unsigned type.
✅
2892
Apparent: Negative value implicitly converted
to an unsigned type.
✅
2893
Suspicious: Negative value implicitly
converted to an unsigned type.
✅
2894
Possible: Negative tainted value implicitly
converted to an unsigned type.
✅
2895
Constant: Negative value cast to an unsigned
type.
✅
2896
Definite: Negative value cast to an unsigned
type.
✅
2897
Apparent: Negative value cast to an unsigned
type.
✅
2898
Suspicious: Negative value cast to an
unsigned type.
✅
2899
Possible: Negative tainted value cast to an
unsigned type.
✅
2900
Constant: Positive integer value truncated by
implicit conversion to a smaller unsigned
type.
✅
2901
Definite: Positive integer value truncated by
implicit conversion to a smaller unsigned
type.
✅
2902
Apparent: Positive integer value truncated by
implicit conversion to a smaller unsigned
type.
✅
2903
Suspicious: Positive integer value truncated
by implicit conversion to a smaller unsigned
type.
✅
2904
Possible: Positive integer tainted value
truncated by implicit conversion to a smaller
unsigned type.
✅
Page 154


---
*Page 154*

Message ID
Message Text
Analyzer
Dataflow
2905
Constant: Positive integer value truncated by
cast to a smaller unsigned type.
✅
2906
Definite: Positive integer value truncated by
cast to a smaller unsigned type.
✅
2907
Apparent: Positive integer value truncated by
cast to a smaller unsigned type.
✅
2908
Suspicious: Positive integer value truncated
by cast to a smaller unsigned type.
✅
2909
Possible: Positive integer tainted value
truncated by cast to a smaller unsigned type.
✅
Page 155


---
*Page 155*
