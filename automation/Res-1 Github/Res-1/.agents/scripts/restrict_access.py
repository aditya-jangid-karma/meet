import sys
import json
import os

def main():
    try:
        # Read the payload from Antigravity via stdin
        payload = json.loads(sys.stdin.read())
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})
        
        # Load the ignore list
        ignore_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ignore.json")
        if not os.path.exists(ignore_file):
            print(json.dumps({"decision": "allow"}))
            return
            
        with open(ignore_file, "r") as f:
            data = json.load(f)
            ignored_paths = data.get("ignored_paths", [])
            
        # Determine the target path based on the tool
        target_path = ""
        if tool_name == "view_file":
            target_path = args.get("AbsolutePath", "")
        elif tool_name in ["replace_file_content", "write_to_file"]:
            target_path = args.get("TargetFile", "")
        elif tool_name == "list_dir":
            target_path = args.get("DirectoryPath", "")
        elif tool_name == "grep_search":
            target_path = args.get("SearchPath", "")
        elif tool_name == "find_by_name":
            target_path = args.get("SearchDirectory", "")
            
        if target_path:
            target_path = os.path.abspath(target_path)
            for ip in ignored_paths:
                ignored_abs = os.path.abspath(ip)
                # Check if target_path is exactly the ignored path, or inside it
                if target_path == ignored_abs or target_path.startswith(ignored_abs + os.sep):
                    print(json.dumps({
                        "decision": "deny", 
                        "reason": f"Access to this path is restricted by ignore.json"
                    }))
                    return
                    
        # If it doesn't match any ignored paths, allow it
        print(json.dumps({"decision": "allow"}))
        
    except Exception as e:
        # On error, fail open or closed depending on preference; failing open is safer for agent stability
        print(json.dumps({"decision": "allow", "reason": f"Hook error: {str(e)}"}))

if __name__ == "__main__":
    main()
