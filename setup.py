"""
Setup script for OpenWorks Prospect Intelligence
Ensures the app package is importable in Streamlit Cloud
"""
from setuptools import setup, find_packages

setup(
    name="openworks-prospect-intelligence",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "streamlit>=1.28.0",
        "plotly>=5.18.0",
        "folium>=0.15.0",
        "streamlit-folium>=0.15.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0.0",
        "google-generativeai>=0.3.0",
        "anthropic>=0.75.0",
        "google-genai>=1.56.0",
        "boto3>=1.34.0",
        "scikit-learn>=1.3.0",
        "fuzzywuzzy>=0.18.0",
        "python-Levenshtein>=0.23.0",
        "openpyxl>=3.1.0",
        "usaddress>=0.5.16",
        "geopy>=2.4.1",
        "jsonschema>=4.25.1",
    ],
    python_requires=">=3.12",
)
