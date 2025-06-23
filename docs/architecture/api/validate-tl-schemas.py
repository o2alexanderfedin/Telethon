#!/usr/bin/env python3
"""
Validation script for Voice Transcription TL Schemas in Telethon
This script verifies that all required TL definitions exist and are properly integrated.
"""

import os
import sys
import re
from pathlib import Path


class TLSchemaValidator:
    """Validates TL schema definitions for voice transcription"""
    
    def __init__(self, telethon_path):
        self.telethon_path = Path(telethon_path)
        self.api_tl = self.telethon_path / "telethon_generator" / "data" / "api.tl"
        self.errors = []
        self.warnings = []
        
    def validate(self):
        """Run all validation checks"""
        print("🔍 Validating Voice Transcription TL Schemas...")
        print(f"📁 Telethon path: {self.telethon_path}")
        print("-" * 50)
        
        # Check if api.tl exists
        if not self.api_tl.exists():
            self.errors.append(f"api.tl not found at {self.api_tl}")
            return False
            
        # Read the TL file
        with open(self.api_tl, 'r') as f:
            content = f.read()
            
        # Validate each required schema
        schemas = [
            {
                'name': 'messages.transcribeAudio',
                'pattern': r'messages\.transcribeAudio#269e9a49.*?= messages\.TranscribedAudio;',
                'expected_hex': '269e9a49',
                'line_hint': 2339
            },
            {
                'name': 'messages.rateTranscribedAudio', 
                'pattern': r'messages\.rateTranscribedAudio#7f1d072f.*?= Bool;',
                'expected_hex': '7f1d072f',
                'line_hint': 2340
            },
            {
                'name': 'updateTranscribedAudio',
                'pattern': r'updateTranscribedAudio#84cd5a.*?= Update;',
                'expected_hex': '84cd5a',
                'line_hint': 393
            },
            {
                'name': 'messages.transcribedAudio',
                'pattern': r'messages\.transcribedAudio#cfb9d957.*?= messages\.TranscribedAudio;',
                'expected_hex': 'cfb9d957',
                'line_hint': 1500
            },
            {
                'name': 'documentAttributeAudio (voice flag)',
                'pattern': r'documentAttributeAudio#.*?voice:flags\.10\?true.*?= DocumentAttribute;',
                'expected_hex': '9852f9c6',
                'line_hint': 595
            }
        ]
        
        print("📋 Checking required schemas:\n")
        
        for schema in schemas:
            self._validate_schema(content, schema)
            
        # Check for generated Python files
        print("\n📦 Checking generated Python files:\n")
        self._check_generated_files()
        
        # Summary
        print("\n" + "=" * 50)
        if self.errors:
            print(f"❌ Validation failed with {len(self.errors)} error(s):")
            for error in self.errors:
                print(f"   • {error}")
        else:
            print("✅ All voice transcription schemas are valid!")
            
        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"   • {warning}")
                
        return len(self.errors) == 0
        
    def _validate_schema(self, content, schema):
        """Validate a single schema definition"""
        name = schema['name']
        pattern = schema['pattern']
        
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            print(f"✅ {name}")
            
            # Verify hex ID if present
            if 'expected_hex' in schema:
                hex_match = re.search(f"#{schema['expected_hex']}", match.group(0))
                if not hex_match:
                    self.warnings.append(
                        f"{name}: Expected hex ID #{schema['expected_hex']} not found"
                    )
            
            # Show location hint
            if 'line_hint' in schema:
                lines = content[:match.start()].count('\n') + 1
                print(f"   Found at line ~{lines} (expected ~{schema['line_hint']})")
                
        else:
            self.errors.append(f"{name}: Schema definition not found")
            print(f"❌ {name} - NOT FOUND")
            
    def _check_generated_files(self):
        """Check if Python files are generated from TL schemas"""
        generated_files = [
            {
                'path': 'telethon/tl/functions/messages/transcribe_audio.py',
                'class': 'TranscribeAudioRequest'
            },
            {
                'path': 'telethon/tl/functions/messages/rate_transcribed_audio.py',
                'class': 'RateTranscribedAudioRequest'
            },
            {
                'path': 'telethon/tl/types/update_transcribed_audio.py',
                'class': 'UpdateTranscribedAudio'
            }
        ]
        
        for file_info in generated_files:
            file_path = self.telethon_path / file_info['path']
            if file_path.exists():
                print(f"✅ {file_info['path']}")
                
                # Check if class exists in file
                with open(file_path, 'r') as f:
                    if file_info['class'] in f.read():
                        print(f"   Class {file_info['class']} found")
                    else:
                        self.warnings.append(
                            f"{file_info['path']}: Class {file_info['class']} not found"
                        )
            else:
                self.warnings.append(f"Generated file not found: {file_info['path']}")
                print(f"⚠️  {file_info['path']} - NOT FOUND")
                

def main():
    """Main entry point"""
    # Determine Telethon path
    if len(sys.argv) > 1:
        telethon_path = sys.argv[1]
    else:
        # Try to find Telethon in workspace
        workspace_telethon = Path(__file__).parent.parent.parent / "Telethon"
        if workspace_telethon.exists():
            telethon_path = workspace_telethon
        else:
            print("❌ Error: Please provide path to Telethon repository")
            print("Usage: python validate-tl-schemas.py /path/to/Telethon")
            sys.exit(1)
            
    # Run validation
    validator = TLSchemaValidator(telethon_path)
    success = validator.validate()
    
    # Suggest next steps
    if success:
        print("\n🚀 Next Steps:")
        print("1. Run 'python setup.py gen tl' to regenerate Python files")
        print("2. Run integration tests to verify functionality")
        print("3. Implement high-level API wrapper for easy usage")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()