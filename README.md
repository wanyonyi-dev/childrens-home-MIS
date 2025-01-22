<div align="center">
  <img src="static/img/logo.png" alt="Children's Home Logo" width="200"/>
  <h1>Children's Home Management System</h1>
  
  [![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
  [![Flask](https://img.shields.io/badge/Flask-2.x-green.svg)](https://flask.palletsprojects.com/)
  [![MongoDB](https://img.shields.io/badge/MongoDB-4.x-success.svg)](https://www.mongodb.com/)
  [![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
</div>

## 📋 Overview

A modern, comprehensive web-based management system designed specifically for children's homes. Built with Flask and MongoDB, this system streamlines administrative tasks, enhances communication, and improves overall operational efficiency.

## ✨ Key Features

### 👥 User Management
- **Multi-role Authentication**
  - Admin, Staff, Teacher, and Nurse roles
  - Role-based access control
  - Secure session management

### 👶 Children Management
- **Comprehensive Records**
  - Digital profile management
  - Photo upload functionality
  - Unique ID generation
  - Automated age tracking

### 📊 Core Functionalities

<details>
<summary><b>Staff Features</b></summary>

- Activity scheduling
- Incident reporting
- Attendance tracking
- Document management
- Emergency contacts
</details>

<details>
<summary><b>Academic Management</b></summary>

- Assessment tracking
- Progress monitoring
- Subject management
- Grade tracking
</details>

<details>
<summary><b>Health Management</b></summary>

- Medical records
- Medication scheduling
- Appointment tracking
- Health monitoring
</details>

<details>
<summary><b>Financial Management</b></summary>

- Transaction tracking
- Donation management
- Financial reporting
- Budget monitoring
</details>

## 🚀 Getting Started

### Prerequisites

- Python 3.x
- MongoDB
- Git

### Installation

1. **Clone the Repository**
   ```bash
   git clone [repository-url]
   cd children-home-system
   ```

2. **Set Up Virtual Environment**
   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   
   # Unix/MacOS
   source .venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure MongoDB**
   ```bash
   # Start MongoDB service
   mongod --dbpath /path/to/data/db
   ```

5. **Run the Application**
   ```bash
   python app.py
   ```

## 🔐 Default Admin Access

Username: System Admin
Password: ADMIN2027254@@