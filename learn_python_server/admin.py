"""
Admin interface for all models in etc_player.
"""
from django.contrib import admin
from learn_python_server.models import (
    Course,
    Enrollment,
    StudentRepository,
    Student
)
from django import forms
