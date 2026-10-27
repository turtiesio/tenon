#!/bin/sh
# Fixture for repros 01 and 02.  Creates /tmp/tq with a jail directory, an outside directory
# and a symlink inside the jail that points outside.  Run the repros from /tmp/tq:
#   ./setup-fs.sh && cd /tmp/tq && tenon run <repro>.tn      (re-run setup between runs: 02 mutates it)
rm -rf /tmp/tq && mkdir -p /tmp/tq/jail /tmp/tq/outside
echo hi > /tmp/tq/jail/in.txt
echo SECRET > /tmp/tq/outside/secret.txt
ln -s ../outside /tmp/tq/jail/link
