#!/usr/bin/env python3
"""
Database migration script to add phone and subject columns to contact_message table
"""

import sqlite3
import os

def update_database():
    # Path to the database file
    db_path = 'navyug.db'
    
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found!")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if phone column exists
        cursor.execute("PRAGMA table_info(contact_message)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add phone column if it doesn't exist
        if 'phone' not in columns:
            print("Adding 'phone' column to contact_message table...")
            cursor.execute("ALTER TABLE contact_message ADD COLUMN phone VARCHAR(20)")
            print("✓ Phone column added successfully")
        else:
            print("✓ Phone column already exists")
        
        # Add subject column if it doesn't exist
        if 'subject' not in columns:
            print("Adding 'subject' column to contact_message table...")
            cursor.execute("ALTER TABLE contact_message ADD COLUMN subject VARCHAR(50)")
            print("✓ Subject column added successfully")
        else:
            print("✓ Subject column already exists")
        
        # Commit the changes
        conn.commit()
        
        # Verify the changes
        cursor.execute("PRAGMA table_info(contact_message)")
        updated_columns = cursor.fetchall()
        print("\nUpdated contact_message table structure:")
        for column in updated_columns:
            print(f"  - {column[1]} ({column[2]})")
        
        print("\n✅ Database updated successfully!")
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    update_database()
