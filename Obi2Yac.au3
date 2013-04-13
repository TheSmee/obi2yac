#Region ;**** Directives created by AutoIt3Wrapper_GUI ****
#AutoIt3Wrapper_Icon=Obi2Yac.ico
#AutoIt3Wrapper_Outfile=Obi2Yac.exe
#AutoIt3Wrapper_Res_Comment=This script is designed to do name substitutions based on a phone number located in local access database.  If name is not found, it will query OpenCNAM/WhitePages.com
#AutoIt3Wrapper_Res_Description=Obi to YAC Caller ID Reverse Lookup
#AutoIt3Wrapper_Res_Fileversion=1.0.0.41
#AutoIt3Wrapper_Res_Fileversion_AutoIncrement=y
#AutoIt3Wrapper_Res_Language=1033
#EndRegion ;**** Directives created by AutoIt3Wrapper_GUI ****
#cs ----------------------------------------------------------------------------

 AutoIt Version: 3.3.8.1
 Author:         Carlos Am�zaga
 Licence: Apache License 2.0.  Free to modify at will, but hopefully you post your changes so other Obi users benefit. :-)

 Script Function:
	This script is designed to do name substitutions based on a phone number located in local access database.  If the name is not found in the
	local database, it will	query OpenCNAM/WhitePages.com and hope it gets lucky during it's query.  Failing that, it returns NAME UNAVAILABLE
	for CNAM.  Results are then broadcast to Yac listeners defined in database or Growl if enabled.  All successful  queries are cached to
	improve speed during future calls. This script runs as a Syslog server and is designed to work with an Obi set to forward Syslog data to PC
	where Obi2Yac is running.  Your mileage may vary.

	You can find YAC here: http://www.sunflowerhead.com/software/yac/
	You can find Growl for Windows here: http://www.growlforwindows.com/gfw/
	You can find Growl for Android here: https://play.google.com/store/apps/details?id=com.growlforandroid.client

Access Database Tables are as follows:
	CallLogs: Log of all received calls
	Listeners: PCs which will receive YAC broadcasts
	ListenerTypes: Currently defines listener types Obi2Yac can send too.  YAC/NCID are listed, but I never got around to doing NCID broadcasts.
	Substitutions: Your personal subsitutions.  You can add both Obi or regular numbers.
	SubstitutionsCache: All successful  queries to OpenCNAM/WhitePages.com are cached here to avoid lookups & increase spead of CID broadcast

Obi2Yac uses an INI file to define the following:
	APIKey: WhitePages.com API Key.  If defined, lookups will will occur after OpenCNAM query.
	GrowlEnable: If defined, will register with Growl if installed on local PC and send CID for broadcast.
	SysLogIP: If defined, will bind to this IP for Syslog.  Do not use 127.0.0.1. If not defined, will bing to first IP it finds.
	SysLogPort: If defined, will bind to that port via UDP. Otherwise it will bind to port 514 UDP.
	NoBreak: If set to 0, will prevent App exit/pause via Systray + Right click.

#ce ----------------------------------------------------------------------------

; Script Start

$listObiProcess = ProcessList("Obi2Yac.exe")
If $listObiProcess[0][0] > 1 Then
	MsgBox(0, "Error", "Process Already Running. Exiting....")
	Exit
EndIf

#include <String.au3>
#include <Date.au3>
#include <array.au3> ; Thanks zatorg: http://www.autoitscript.com/forum/index.php?showtopic=45189&hl=Asock
#include <_Growl.au3> ;Thanks Markus Mohnen <markus.mohnen@googlemail.com>: http://www.autoitscript.com/forum/topic/95141-growl-for-windows-udf/
#include <_StringStripChars.au3> ;Thanks amel27 & G.Sandler (a.k.a MsCreatoR): http://www.autoitscript.com/forum/topic/69186-stringstripchr/

;Don't allow pause
AutoItSetOption ( "TrayAutoPause" , 0)

;Don't allow exit via Systray.  Must Kill PID.  Change via INI
$NoBreak = ReadINI("NoBreak", 0)
Break($NoBreak)

;Define Access Database Name Here
Global $dbname = @ScriptDir & "\Obi2Yac.mdb"

;Define CID Syslog String to Look for Here
Global $CIDString = "[SLIC] CID to deliver:"

;What IP to use for Syslog
$SysLogIP = ReadINI("SysLogIP", @IPAddress1)

;What port to use for Syslog
$SysLogPort = ReadINI("SysLogPort", 514)

; Start The UDP Services
;==============================================
UDPStartup()

; Bind to a SOCKET as if Sysloger.  Will bind to Local IP1.  Can be a problem if you have more than one IP.
;==============================================
$socket = UDPBind($SysLogIP, $SysLogPort)
If @error <> 0 Then
	MsgBox(0, "Error", "Unable to bind to " & $SysLogIP & " on port 514")
	Exit
EndIf

;Wait for data and do things when received.
While 1
    $data = UDPRecv($socket, 100, 1)
    If $data <> "" Then
		$stringData = BinaryToString($data)

		;Output Syslog Data for Curious People
        ConsoleWrite($stringData & @CRLF)

		$CheckSyslogData = StringInStr( $stringData, $CIDString, 0, 1, 1)

		If $CheckSyslogData > 0 Then
			;Start the Lookups
			ObiPhoneCall($stringData)
		EndIf
    EndIf
    Sleep(100)
WEnd

Func ObiPhoneCall($SyslogString)
	;Parse number from Syslog string and format
	$phoneNumber = 	FormatPhone($SyslogString)

	;If no CNAM in string then start phone lookup here.  Local database first, otherwise OpenCNAM.  If neither return a hit
	;and you have a defined API key in INI file, it will query Whitepages.com as a last option.  Results ar cached in database
	;for next call.

	$CIDName = LookupPhoneNumber($phoneNumber[2], StringLen($phoneNumber[1]), $phoneNumber[1])

	;Write output to console for curious people...
	ConsoleWrite(@CRLF & "Name: " & $CIDName & @CRLF)
	ConsoleWrite("Number: " & StringRegExpReplace($phoneNumber[2], "\A(\d{1})(\d{3})(\d{3})(\d{4})","($2) $3-$4") & @CRLF)

	;Broadcast number lookup results to YAC clients.  It will also send out Growl if it is enabled in INI file.
	$formatedPhone = Broadcast($CIDName, $phoneNumber[2])

	;Log results in database
	LogCID($CIDName, $formatedPhone)

	;Reduce working set to free up memory
	SelfReduceMemory()

	Return
EndFunc

Func FormatPhone($SyslogString)
	$phoneNumberSyslogL = StringSplit($SyslogString, $CIDString, 1)
	$phoneNumber = StringSplit(StringStripWS($phoneNumberSyslogL[2],3), "' ", 1)
	$phoneNumber[1] = _StringStripChars($phoneNumber[1], "'", 3, 0, 0)
	$phoneNumber[2] = StringLeft($phoneNumber[2], StringLen($phoneNumber[2]) - 2)
	Return($phoneNumber)
EndFunc

Func LookupPhoneNumber($phoneNumber, $phoneLen, $phoneCNAM)
	$query  = "SELECT Name, Number FROM Substitutions WHERE Number = '" & StringRight($phoneNumber,10) & "' UNION SELECT Name, Number FROM SubstitutionsCache WHERE Number = '" & StringRight($phoneNumber,10) & "'"
	$adoCon = ObjCreate("ADODB.Connection")
	$adoCon.Open("Driver={Microsoft Access Driver (*.mdb)}; DBQ=" & $dbname) ;Use this line if using MS Access 2003 and lower
	;$adoCon.Open ("Provider=Microsoft.Jet.OLEDB.4.0; Data Source=" & $dbname) ;Use this line if using MS Access 2007 and using the .accdb file extension
	$adoRs = ObjCreate ("ADODB.Recordset")
	$adoRs.CursorType = 1
	$adoRs.LockType = 3
	$adoRs.Open ($query, $adoCon)
	$APIKey = ReadINI("APIKey", 0)

	With $adoRs
		If $adoRs.RecordCount Then
		$count=0
			While Not .EOF
				$count=$count+1
				$theName = $adoRs.Fields("Name").value
			.MoveNext
			WEnd
		ElseIf $phoneLen > 0 Then
			$theName = $phoneCNAM
		Else
			$sData = InetRead("https://api.opencnam.com/v2/phone/+" & $phoneNumber)
			$nBytesRead = @extended
			If $nBytesRead > 0 Then
				$theName = BinaryToString($sData)
				CacheCID($theName, StringRight($phoneNumber,10))
			ElseIf $APIKey <> 0 Then
				$url = 'http://api.whitepages.com/reverse_phone/1.0/?phone=' & StringRight($phoneNumber,10) & ';api_key=' & $APIKey
				$objhttp = ObjCreate("MSXML2.XMLhttp.3.0")
				$objhttp.Open("GET", $url, false)
				$objhttp.Send
				$data = $objhttp.responseText

				$oNodeResult = _StringBetween($data, "<wp:result ", "/>")
				$oResult = _StringBetween($oNodeResult[0], 'wp:type="', '"')
				$oCode = _StringBetween($oNodeResult[0], 'wp:code="', '"')

				If $oResult[0] = "success" AND $oCode[0] = "Found Data" Then
					$oNodeListing = _StringBetween($data, "<wp:listing>", "</wp:listing>")
					$oCity =  _StringBetween($oNodeListing[0], "<wp:city>", "</wp:city>")
					$oState =  _StringBetween($oNodeListing[0], "<wp:state>", "</wp:state>")
					$oDisplayName = _StringBetween($oNodeListing[0], "<wp:displayname>", "</wp:displayname>")
					$oCarrier =  _StringBetween($oNodeListing[0], "<wp:carrier>", "</wp:carrier>")

					If (UBound($oDisplayName)) > 0 Then
						$theDisplayName = $oDisplayName[0]
					ElseIf (UBound($oCarrier)) > 0 Then
						$theDisplayName = $oCity[0] & ", " & $oState[0] &  " - " & $oCarrier[0]
					Else
						$theDisplayName = ""
					EndIf

					$theName = $theDisplayName
					CacheCID($theName, StringRight($phoneNumber,10))
				Else
					$theName = "NAME UNAVAILABLE"
				EndIf
			Else
				$theName = "NAME UNAVAILABLE"
			EndIf
		EndIf
	EndWith
	$adoCon.Close
	Return($theName)
EndFunc

Func Broadcast($aName, $aNumber)
	$query  = "SELECT * FROM Listeners WHERE ACTIVE=1"
	$adoCon = ObjCreate("ADODB.Connection")
	$adoCon.Open("Driver={Microsoft Access Driver (*.mdb)}; DBQ=" & $dbname) ;Use this line if using MS Access 2003 and lower
	;$adoCon.Open ("Provider=Microsoft.Jet.OLEDB.4.0; Data Source=" & $dbname) ;Use this line if using MS Access 2007 and using the .accdb file extension
	$adoRs = ObjCreate ("ADODB.Recordset")
	$adoRs.CursorType = 1
	$adoRs.LockType = 3
	$adoRs.Open ($query, $adoCon)

	$phoneNumber = StringRegExpReplace($aNumber, "\A(\d{1})(\d{3})(\d{3})(\d{4})","($2) $3-$4")

	If ReadINI("GrowlEnable", 0) = 1 Then
		Local $notifications[1][1] = [["Notifcation"]]
		Local $id=_GrowlRegister("Obi2Yac", $notifications, "http://www.autoitscript.com/autoit3/files/graphics/au3.ico")
		_GrowlNotify($id, $notifications[0][0], "Call From: " & $phoneNumber , $aName & " : "& _Now())
	EndIf

	With $adoRs
		If $adoRs.RecordCount Then
		TCPStartup()
		$count=0
			While Not .EOF
				$count=$count+1
				$szIPADDRESS = $adoRs.Fields("IP").value  ;Retrieve value by field name
				$theType = $adoRs.Fields("Type").value    ;Retrieve value by field name
				If $theType = 1 Then
					$PingHost = Ping($szIPADDRESS, 10)
					If $PingHost Then
						$ConnectedSocket = TCPConnect($szIPADDRESS, "10629")
						TCPSend($ConnectedSocket, StringToBinary("@CALL" & StringLeft($aName, 25) & "~" & $phoneNumber, 4))
						TCPCloseSocket($ConnectedSocket)
					EndIf
				EndIf
			.MoveNext
			WEnd

			TCPShutdown()
		EndIf

	EndWith

	$adoCon.Close

	Return($phoneNumber)
EndFunc

Func CacheCID($aName, $aNumber)
	$query  = "INSERT INTO SubstitutionsCache ([Name], [Number]) VALUES ('" & StringReplace($aName, "'", "''") & "', '" & $aNumber &"')"
	$adoCon = ObjCreate("ADODB.Connection")
	$adoCon.Open("Driver={Microsoft Access Driver (*.mdb)}; DBQ=" & $dbname) ;Use this line if using MS Access 2003 and lower
	;$adoCon.Open ("Provider=Microsoft.Jet.OLEDB.4.0; Data Source=" & $dbname) ;Use this line if using MS Access 2007 and using the .accdb file extension
	$adoCon.Execute($query)
	$adoCon.Close
	Return
EndFunc

Func LogCID($aName, $aNumber)
	$query  = "INSERT INTO CallLogs ([Name], [Number]) VALUES ('" & StringReplace($aName, "'", "''") & "', '" & $aNumber &"')"
	$adoCon = ObjCreate("ADODB.Connection")
	$adoCon.Open("Driver={Microsoft Access Driver (*.mdb)}; DBQ=" & $dbname) ;Use this line if using MS Access 2003 and lower
	;$adoCon.Open ("Provider=Microsoft.Jet.OLEDB.4.0; Data Source=" & $dbname) ;Use this line if using MS Access 2007 and using the .accdb file extension
	$adoCon.Execute($query)
	$adoCon.Close
	Return
EndFunc

Func ReadINI($theKey, $theDefault)
	$query = IniRead(@ScriptDir& "\Obi2Yac.ini", "Obi2YacConfig", $theKey, $theDefault)
	Return($query)
EndFunc

Func SelfReduceMemory()
	DllCall("psapi.dll", "int", "EmptyWorkingSet", "long", -1)
	Return
EndFunc   ;==>_SelfReduceMemory

Func OnAutoItExit()
    UDPCloseSocket($socket)
    UDPShutdown()
EndFunc