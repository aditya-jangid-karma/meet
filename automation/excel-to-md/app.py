import os
import tempfile
import shutil
from flask import Flask, render_template, request, jsonify
import pandas as pd
from markitdown import MarkItDown
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Initialize MarkItDown converter
md_converter = MarkItDown()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    output_dir = request.form.get('output_folder', '').strip()
    
    try:
        skip_rows = int(request.form.get('skip_rows', 4))
    except ValueError:
        skip_rows = 4

    # Get uploaded files
    files = request.files.getlist('files')

    if not files or files[0].filename == '':
        return jsonify({"status": "error", "message": "No files or folder uploaded."}), 400

    if not output_dir:
        return jsonify({"status": "error", "message": "Output destination folder is required."}), 400

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    supported_extensions = ('.xlsx', '.docx', '.pdf')
    results = []
    success_count = 0

    # Create a temporary directory to save the uploaded files for processing
    temp_dir = tempfile.mkdtemp()
    
    try:
        for file in files:
            if file.filename:
                # Handle browsers that send relative paths like 'folder/file.xlsx'
                filename = os.path.basename(file.filename)
                ext_lower = os.path.splitext(filename)[1].lower()
                
                if ext_lower in supported_extensions:
                    # Save to temporary folder
                    temp_path = os.path.join(temp_dir, secure_filename(filename))
                    file.save(temp_path)
                    
                    name_without_ext = os.path.splitext(filename)[0]
                    output_path = os.path.join(output_dir, f"{name_without_ext}.md")
                    
                    try:
                        if ext_lower == '.xlsx':
                            # Convert Excel using Pandas
                            df = pd.read_excel(temp_path, skiprows=skip_rows)
                            
                            # Remove 'Unnamed: X' from empty column headers
                            df.columns = ["" if str(col).startswith("Unnamed:") else col for col in df.columns]
                            
                            df = df.fillna("")
                            markdown_table = df.to_markdown(index=False)
                            
                            with open(output_path, "w", encoding="utf-8") as f:
                                f.write(f"## {name_without_ext}\n\n")
                                f.write(markdown_table)
                        
                        elif ext_lower in ['.docx', '.pdf']:
                            # Convert Word/PDF using MarkItDown
                            result = md_converter.convert(temp_path)
                            with open(output_path, "w", encoding="utf-8") as f:
                                f.write(result.text_content)
                                
                        results.append({"file": filename, "status": "Success"})
                        success_count += 1
                    except Exception as e:
                        results.append({"file": filename, "status": f"Error: {str(e)}"})
    finally:
        # Clean up temporary directory when done
        shutil.rmtree(temp_dir)

    if len(results) == 0:
        return jsonify({"status": "error", "message": "No valid supported files (.xlsx, .docx, .pdf) were found in your upload."}), 404

    return jsonify({
        "status": "success", 
        "message": f"Processed {len(results)} valid files. {success_count} successful.",
        "details": results
    })

if __name__ == '__main__':
    # Run the Flask app on localhost, port 5000
    app.run(host='127.0.0.1', port=5000, debug=True)
