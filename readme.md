# obi2yac
### AutoIt Version: 3.3.14.5
### Author: Carlos Amézaga
### Licence: Apache License 2.0.  Free to modify at will, but hopefully you post your changes so other Obi users benefit. :-)

### Script Function:
> This script is designed to do name substitutions based on a phone number located in local access database.  If the name is not found in the local database, it will query OpenCNAM/WhitePages.com and hope it gets lucky during it's query.  Failing that, it returns NAME UNAVAILABLE for CNAM.  Queries using Whitepages.com will only occur if you have a valid APIKey defined in the INI. Results are then broadcast to Yac listeners defined in database, Growl or PushBullet if enabled.  All successful queries are cached to improve speed during future calls. This script runs as a Syslog server and is designed to work with an Obi set to forward Syslog data to PC where Obi2Yac is running.  Your mileage may vary.

- You can find my program here: https://github.com/thesmee/obi2yac/
- You can find YAC here: http://www.sunflowerhead.com/software/yac/
- You can find Growl for Windows here: http://www.growlforwindows.com/gfw/
- You can find Growl for Android here: https://play.google.com/store/apps/details?id=com.growlforandroid.client
- More information on PushBullet: https://www.pushbullet.com

### Access Database Tables are as follows:
- CallLogs: Log of all received calls
- Listeners: PCs which will receive YAC broadcasts
- ListenerTypes: Currently defines listener types Obi2Yac can send too.  YAC/NCID are listed, but I never got around to doing NCID broadcasts.
- Substitutions: Your personal substitutions.  You can add both Obi or regular numbers.
- SubstitutionsCache: All successful  queries to OpenCNAM/WhitePages.com are cached here to avoid lookups & increase spead of CID broadcast

### Obi2Yac uses an INI file to define the following:
- APIKey: WhitePages.com API Key.  If defined, lookups will will occur after OpenCNAM query.
- GrowlEnable: If defined, will register with Growl if installed on local PC and send CID for broadcast.
- PushBulletlEnable: If defined, will broadcast CID information to PushBullet.  Must enter API key in INI under PushBulletlKey.
- SysLogIP: If defined, will bind to this IP for Syslog.  Do not use 127.0.0.1. If not defined, will bind to first IP it finds.
- SysLogPort: If defined, will bind to that port via UDP. Otherwise it will bind to port 514 UDP.
- NoBreak: If set to 0, will prevent App exit/pause via Systray + Right click.
