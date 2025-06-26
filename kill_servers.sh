#!/bin/bash

xargs kill < server_pids.txt
rm server_pids.txt