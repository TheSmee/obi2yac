;===============================================================================
; Function Name:         _StringStripChars()
; Description:           Strip (replace) certain character(s) from the String.
;
; Parameter(s):          $sString - String that character(s) will be striped from.
;                        $sSubString - The character(s) to strip.
;                        $iFlag [Optional] - Defines the behaviour of stripping process (see Returned value(s)).
;                        $iCount [Optional] - Defines how many times to perform the strip (see Returned value(s)).
;                        $iGroupChars [Optional] - If this parameter is 1 (default is 0), then all characters in $sSubString grouped and replaced seperately.
;
; Requirement(s):        AutoIt 3.2.8.1 +
;
; Return Value(s):       On seccess - Return new string with stripped characters accourding to given $Flag and $iCount:
;                               $iFlag = 0 (default) replace the character(s) in $sString whetewer it founded - with this flag,
;                                   also @extended is set to number of $sSubString replaces in $sString.
;                               $iFlag = 1 replace the character(s) from the Left side of $sString.
;                               $iFlag = 2 replace the character(s) from the Right side of $sString.
;                               $iFlag = 3 replace the character(s) from the Bouth sides of $sString.
;
;                               $iCount = 0 replace all $sSubString char(s).
;                               $iCount > 0 replace that much $sSubString char(s).
;
;                        On failure - If lenght of given string is equel 0, then @error set to 1 and returned initial $sString.
;
; Author(s):             amel27, mod. by G.Sandler a.k.a MsCreatoR
;===============================================================================
Func _StringStripChars($sString, $sSubString, $iFlag = 0, $iCount = 0, $iGroupChars = 0)
    If StringLen($sString) = 0 Then Return SetError(1, 0, $sString)

    Local $sGroupChar_a = '(', $sGroupChar_b = ')'
    If $iCount < 0 Then Local $sGroupChar_a = '[', $sGroupChar_b = ']'

    $sSubString = StringRegExpReplace($sSubString, '([][{}()|.?+*^$])', '1')

    If $iGroupChars = 1 Then $sSubString = '[' & $sSubString & ']'
ConsoleWrite($sSubString &@CRLF)
    Local $sPattern = '(?i)' & $sGroupChar_a & $sSubString & $sGroupChar_b
    Local $sPattern_Count = '{1,' & $iCount & '}'

    If $iCount <= 0 Then $sPattern_Count = '+'
    If $iFlag <> 0 Then $iCount = 0
    If $iFlag = 1 Then $sPattern = '(?i)^' & $sGroupChar_a & $sSubString & $sGroupChar_b & $sPattern_Count
    If $iFlag = 2 Then $sPattern = '(?i)' & $sGroupChar_a & $sSubString & $sGroupChar_b & $sPattern_Count & '$'
    If $iFlag = 3 Then $sPattern = '(?i)^' & $sGroupChar_a & $sSubString & $sGroupChar_b & $sPattern_Count & '|' & _
        $sGroupChar_a & $sSubString & $sGroupChar_b & $sPattern_Count & '$'

    $sString = StringRegExpReplace($sString, $sPattern, '', $iCount)
    Return SetExtended(@extended, $sString)
EndFunc
