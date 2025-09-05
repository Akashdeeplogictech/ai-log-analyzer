#!/usr/bin/env python3
"""
Simple script to debug Ollama connection and model issues
"""

import ollama
import json
import sys

def debug_ollama():
    print("?? Debugging Ollama Connection...")
    
    try:
        # Test 1: Basic connection
        print("\n1. Testing basic connection...")
        response = ollama.list()
        print(f"   Raw response type: {type(response)}")
        print(f"   Raw response: {response}")
        
        # Test 2: Parse models
        print("\n2. Parsing models...")
        if isinstance(response, dict):
            models = response.get('models', [])
            print(f"   Models type: {type(models)}")
            print(f"   Models count: {len(models)}")
            
            if models:
                print("   First model details:")
                first_model = models[0]
                print(f"     Type: {type(first_model)}")
                print(f"     Content: {first_model}")
                
                if isinstance(first_model, dict):
                    print("     Available keys:", list(first_model.keys()))
                    for key in ['name', 'model', 'title', 'id']:
                        if key in first_model:
                            print(f"     {key}: {first_model[key]}")
            else:
                print("   ? No models found!")
                print("   Run: ollama pull llama2:7b")
                return False
        else:
            print(f"   ? Unexpected response format: {type(response)}")
            return False
        
        # Test 3: Try simple generation
        if models:
            print("\n3. Testing generation...")
            
            # Find a usable model name
            model_name = None
            first_model = models[0]
            
            if isinstance(first_model, dict):
                model_name = (first_model.get('name') or 
                             first_model.get('model') or 
                             first_model.get('id'))
            else:
                model_name = str(first_model)
            
            if model_name:
                print(f"   Using model: {model_name}")
                try:
                    gen_response = ollama.generate(
                        model=model_name,
                        prompt="Say 'Hello'",
                        options={
                            'num_predict': 3,
                            'temperature': 0
                        }
                    )
                    print(f"   Generation successful!")
                    print(f"   Response: {gen_response.get('response', 'No response key')[:100]}")
                    return True
                    
                except Exception as e:
                    print(f"   ? Generation failed: {e}")
                    print(f"   This suggests the model name '{model_name}' is incorrect")
                    
                    # Try alternative model names
                    alternatives = [
                        'llama2:7b',
                        'llama2:latest', 
                        'llama2',
                        str(first_model).split(':')[0] if ':' in str(first_model) else None
                    ]
                    
                    for alt_name in alternatives:
                        if alt_name and alt_name != model_name:
                            try:
                                print(f"   Trying alternative: {alt_name}")
                                gen_response = ollama.generate(
                                    model=alt_name,
                                    prompt="Hi",
                                    options={'num_predict': 2}
                                )
                                print(f"   ? Success with: {alt_name}")
                                return True
                            except Exception as e2:
                                print(f"   Failed: {e2}")
                                continue
            else:
                print("   ? Could not determine model name")
        
        return False
        
    except Exception as e:
        print(f"? Debug failed with error: {e}")
        print(f"   Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_ollama_service():
    """Check if Ollama service is running"""
    print("\n?? Checking Ollama Service...")
    
    import subprocess
    import psutil
    
    # Check if ollama process is running
    ollama_running = False
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if 'ollama' in proc.info['name'].lower():
                print(f"   ? Found Ollama process: PID {proc.info['pid']}")
                ollama_running = True
                break
    except Exception as e:
        print(f"   ? Error checking processes: {e}")
    
    if not ollama_running:
        print("   ? Ollama service not running")
        print("   ?? Start it with: ollama serve")
        return False
    
    # Check if port is listening
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 11434))
        sock.close()
        
        if result == 0:
            print("   ? Ollama port 11434 is open")
        else:
            print("   ? Ollama port 11434 not accessible")
            return False
    except Exception as e:
        print(f"   ? Error checking port: {e}")
        return False
    
    return True

def main():
    print("?? Ollama Diagnostic Tool")
    print("=" * 50)
    
    # Check service first
    service_ok = check_ollama_service()
    
    if service_ok:
        # Run connection debug
        connection_ok = debug_ollama()
        
        if connection_ok:
            print("\n? Ollama appears to be working correctly!")
        else:
            print("\n? Ollama has issues that need to be resolved")
            print("\n?? Try these solutions:")
            print("   1. Restart Ollama: pkill ollama && ollama serve")
            print("   2. Install/reinstall a model: ollama pull llama2:7b")
            print("   3. Check system resources: free -h")
    else:
        print("\n? Ollama service is not running properly")
        print("\n?? Start Ollama service:")
        print("   ollama serve")

if __name__ == "__main__":
    main()