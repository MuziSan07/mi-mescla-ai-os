"""Pytest configuration and shared fixtures"""
import sys
import os

# Make sure src is on the path when running inside Docker
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
