#!/bin/bash
# Alert format: "{{.Timestamp}} | {{.Name}} | {{.DeviceHostName}} | {{.Message}} | {{.Tactic}} | {{.Technique}}"
set -eu

RULE=$1

# writing local log of arguments 
echo $(date +"%d-%m-%Y %T.%3N") - $RULE >> /opt/kaspersky/kuma/correlator/<ID_CORRELATOR>/scripts/bot.log

# escaping spec characters in argument except \s \| 
#RULE=$(echo $RULE | sed 's/[][\~`!@#$%^&*()=+{};:'"'"'"<>/?-]/\\&/g')

#try to beautify alert if arg is like "{{.Timestamp}} | {{.Name}} | {{.DeviceHostName}}"
TIME=$(date -d @$(($(echo $RULE | cut -d "|" -f 1)/1000)))
NAME=$(echo $RULE | cut -d "|" -f 2)
HOST=$(echo $RULE | cut -d "|" -f 3)
MSG=$(echo $RULE | cut -d "|" -f 4)
TAC=$(echo $RULE | cut -d "|" -f 5)
TEC=$(echo $RULE | cut -d "|" -f 6)
TEXT_HTML=$'⚠️Алерт \nПравило: <b>'"$NAME"$'</b> \nВремя: '"$TIME"$' \nХост: '"$HOST"$' \nСообщение: <code>'"$MSG"$'</code> \nТактика: '"$TAC"$' \nТехника: '"$TEC"$''

# Port 16667 holding the bot python script
nc -w 5 127.0.0.1 16667 <<< "$TEXT_HTML"
