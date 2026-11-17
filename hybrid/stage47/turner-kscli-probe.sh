#!/system/bin/sh
exec >> /tmp/kscli-probe.log 2>&1
echo "kscli-probe: start"
i=0
while [ $i -lt 150 ]; do
  grep -q "pid" /tmp/spawn-keystore2-sup.log 2>/dev/null && break
  sleep 0.2; i=$((i+1))
done
sleep 2
export LD_LIBRARY_PATH=/system/etc/hybrid/kscli:/system/lib64/twrp16:/system/lib64
echo "--- CLI list:"
/system/etc/hybrid/kscli/keystore_cli_v2 list
echo "cli rc=$?"
echo "--- NDK probe3 (preload into toybox):"
LD_PRELOAD=/system/etc/hybrid/kscli/libprobe3.so toybox true &
P=$!
sleep 8
kill $P 2>/dev/null
wait $P 2>/dev/null
echo "probe3 finished (rc=$?)"
chmod 644 /tmp/kscli-probe.log
echo "kscli-probe: end"
