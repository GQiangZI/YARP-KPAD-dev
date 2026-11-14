#!/system/bin/sh
# The upstream restore hook can run before the final ODM unmount. Do not
# install a manifest or start the service until twrp.storage.ready is set.
if [ "$(getprop twrp.turner.touch.cached)" = 1 ] && [ -x /tmp/turner-touch/live/bin/touchfeature ]; then
    exit 0
fi
printf '%s\n' 'turner-touch: runtime cache unavailable' >> /tmp/recovery.log
exit 1
