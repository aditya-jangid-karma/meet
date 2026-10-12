from flask import Flask, render_template, request, redirect, url_for, Response
import requests
import json
import math

app = Flask(__name__)

# Input Webhook URL
BITRIX_BASE_URL = "https://karma.bitrix24.in/rest/1360/53a7093vm31bnky8/"
PER_PAGE = 10


# ==========================================
# BITRIX API FETCH FUNCTIONS
# ==========================================

def get_all_tasks():
    """Fetch all tasks handling Bitrix24 REST API pagination."""
    all_tasks = []
    start = 0
    endpoint = BITRIX_BASE_URL + "task.item.list.json"
    
    while True:
        response = requests.get(endpoint, params={"start": start})
        data = response.json()
        tasks = data.get("result", [])
        
        if isinstance(tasks, list):
            all_tasks.extend(tasks)
            
        if "next" in data:
            start = data["next"]
        else:
            break
            
    return all_tasks


def get_all_templates():
    """Fetch all task templates via Bitrix API."""
    all_templates = []
    start = 0
    endpoint = BITRIX_BASE_URL + "tasks.task.template.list.json"
    
    while True:
        response = requests.get(endpoint, params={"start": start})
        data = response.json()
        
        # Depending on the Bitrix REST version, results might be a direct list 
        # or wrapped in a dictionary under 'template'
        res = data.get("result", [])
        if isinstance(res, dict) and "template" in res:
            templates = res.get("template", [])
        else:
            templates = res

        if isinstance(templates, list):
            all_templates.extend(templates)
            
        if "next" in data:
            start = data["next"]
        else:
            break
            
    return all_templates


def get_all_groups():
    """Fetch all workgroups/projects via Bitrix API."""
    all_groups = []
    start = 0
    endpoint = BITRIX_BASE_URL + "sonet_group.get.json"
    
    while True:
        response = requests.get(endpoint, params={"start": start})
        data = response.json()
        groups = data.get("result", [])
        
        if isinstance(groups, list):
            all_groups.extend(groups)
            
        if "next" in data:
            start = data["next"]
        else:
            break
            
    return all_groups


def get_access_permissions():
    """
    Fetch access permissions names. 
    Note: If you need access for a specific user, you might use 'user.access.json' instead.
    """
    endpoint = BITRIX_BASE_URL + "access.name.json"
    response = requests.get(endpoint)
    return response.json().get("result", [])


# ==========================================
# FLASK ROUTES
# ==========================================

# SHOW ALL TASKS
@app.route("/")
def index():
    all_tasks = get_all_tasks()
    
    # 1. Search Filtering
    search_query = request.args.get("search", "").strip()
    if search_query:
        filtered_tasks = [
            t for t in all_tasks 
            if search_query.lower() in str(t.get("TITLE", "")).lower() or 
               search_query in str(t.get("ID", ""))
        ]
    else:
        filtered_tasks = all_tasks

    # 2. Total Count
    total_count = len(filtered_tasks)

    # 3. Pagination Logic
    page = request.args.get("page", 1, type=int)
    total_pages = math.ceil(total_count / PER_PAGE) if total_count > 0 else 1
    
    start_idx = (page - 1) * PER_PAGE
    end_idx = start_idx + PER_PAGE
    paginated_tasks = filtered_tasks[start_idx:end_idx]

    return render_template(
        "index.html", 
        tasks=paginated_tasks, 
        total_count=total_count,
        search_query=search_query,
        page=page,
        total_pages=total_pages
    )


# CREATE
@app.route("/create", methods=["POST"])
def create_task():
    title = request.form.get("title")
    responsible_id = request.form.get("responsible_id", 1360)
    
    # Use tasks.task.add.json instead of task.item.add.json
    endpoint = BITRIX_BASE_URL + "tasks.task.add.json"
    
    payload = {
        "fields": {
            "TITLE": title,
            "RESPONSIBLE_ID": responsible_id
        }
    }
    
    response = requests.post(endpoint, json=payload)
    print("Bitrix Create Response:", response.json())
    
    return redirect(url_for("index"))


# UPDATE
@app.route("/update/<task_id>", methods=["POST"])
def update_task(task_id):
    new_title = request.form.get("title")
    endpoint = BITRIX_BASE_URL + "task.item.update.json"
    payload = {"taskId": task_id, "fields": {"TITLE": new_title}}
    requests.post(endpoint, json=payload)
    return redirect(url_for("index"))


# DELETE
@app.route("/delete/<task_id>", methods=["GET"])
def delete_task(task_id):
    endpoint = BITRIX_BASE_URL + "task.item.delete.json"
    payload = {"taskId": task_id}
    requests.post(endpoint, json=payload)
    return redirect(url_for("index"))


# ==========================================
# JSON DOWNLOAD / PREVIEW ROUTES
# ==========================================

@app.route("/download-json")
def download_json():
    tasks = get_all_tasks()
    json_data = json.dumps(tasks, indent=2, ensure_ascii=False)
    
    return Response(
        json_data,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=bitrix_tasks.json"}
    )


@app.route("/templates")
def show_templates():
    """Route to output the raw JSON list of Task Templates."""
    templates = get_all_templates()
    return Response(
        json.dumps(templates, indent=2, ensure_ascii=False),
        mimetype="application/json"
    )


@app.route("/groups")
def show_groups():
    """Route to output the raw JSON list of Workgroups/Projects."""
    groups = get_all_groups()
    return Response(
        json.dumps(groups, indent=2, ensure_ascii=False),
        mimetype="application/json"
    )


@app.route("/access")
def show_access():
    """Route to output the raw JSON list of Access Permissions."""
    access_data = get_access_permissions()
    return Response(
        json.dumps(access_data, indent=2, ensure_ascii=False),
        mimetype="application/json"
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)