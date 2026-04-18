@echo off
echo Starting test batch...
cd /d c:\Documents\itmo\vkr\backend\src\
python -u tests/test_integration_logic.py > tests/test_out_final.txt 2>&1
echo BATCH_DONE >> tests/test_out_final.txt
