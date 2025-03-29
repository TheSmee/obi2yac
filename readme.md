# obi2yac
### AutoIt Version: 3.3.14.5
### Author: Carlos Amézaga
### Licence: Apache License 2.0.  Free to modify at will, but hopefully you post your changes so other Obi users benefit. :-)

### Script Function:
This script is designed to perform name substitutions based on a phone number located in a local Access database. If the name is not found in the local database, it will query OpenCNAM or WhitePages.com for a match. If no match is found, it will return "NAME UNAVAILABLE" for CNAM. Queries to WhitePages.com will only occur if a valid APIKey is defined in the INI file. Results are then broadcast to YAC listeners defined in the database, as well as to Growl or PushBullet if these options are enabled. All successful queries are cached to improve speed for future calls. This script runs as a Syslog server and is designed to work with an Obi device configured to forward Syslog data to the PC where Obi2Yac is running. Your experience may vary.

- You can find my program here: https://github.com/thesmee/obi2yac/
- You can find YAC here: https://web.archive.org/web/20160808013047/http://www.sunflowerhead.com/software/yac/ (Thanks Jensen Harris!)
    - Note: The original YAC website (http://www.sunflowerhead.com/software/yac) is no longer available.
- You can find Growl for Windows here: https://github.com/briandunnington/growl-for-windows
- You can find Growl for Android here: https://growlforandroid.com
- More information on PushBullet: https://www.pushbullet.com

### Access Database Tables are as follows:
- CallLogs: Log of all received calls.
- Listeners: PCs which will receive YAC broadcasts.
- ListenerTypes: Currently defines listener types Obi2Yac can send too. YAC/NCID are listed, but I never got around to doing NCID broadcasts.
- Substitutions: Your personal substitutions.  You can add both Obi or regular numbers.
- SubstitutionsCache: Deprecated. Was used for all successful queries to OpenCNAM/WhitePages.com which were then cached here to avoid lookups & increase spead of CID broadcast.

### Obi2Yac uses an INI file to define the following:
- DatabaseName: Database name can now be defined. Support for the old mdb or new accdb databases added.
- GrowlEnable: If defined, will register with Growl if installed on local PC and send CID for broadcast.
- PushBulletlEnable: If defined, will broadcast CID information to PushBullet.  Must enter API key in INI under PushBulletlKey.
- SysLogIP: If defined, will bind to this IP for Syslog.  Do not use 127.0.0.1. If not defined, will bind to first IP it finds.
- SysLogPort: If defined, will bind to that port via UDP. Otherwise it will bind to port 514 UDP.
- NoBreak: If set to 0, will prevent App exit/pause via Systray + Right click.
- EnableDTMFTrigger: DTMF Trigger Settings used to trigger an email when a particular number is dialed by an alarm. Can be triggered using speed dials such as 69#, 70# and 71# or a phone number.
- DTMFTrigger1/DTMFTrigger2/DTMFTrigger3: Phone Values that will trigger an email alert. Obi Speed dials can be used such as 69#, 70# and 71#.
- SmtpServer: IP or Name of your local SMTP server.
- FromName: Name that should display in Email From.
- FromAddress: Email address to show in email From.
- ToAddress: Email address to send to.
- EmailSubject: Subject of Email.
- Note: APIKey support has been removed. WhitePages.com and OpenCNAM APIs were depricated.
