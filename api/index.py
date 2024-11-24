from flask import Flask, request, jsonify, send_file
import pydot
import requests
import os
from firebase_admin import credentials, initialize_app, db
from flask_cors import CORS
import tempfile
from datetime import datetime
import json

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Gunakan temporary directory untuk file static
STATIC_FOLDER = tempfile.gettempdir()

firebase_credentials = os.getenv('FIREBASE_CREDENTIALS')
cred_dict = json.loads(firebase_credentials)

cred = credentials.Certificate(cred_dict)
initialize_app(cred, {"databaseURL": "https://silsilah-keluarga-10d90-default-rtdb.firebaseio.com/"})

def load_data():
    """Memuat data keluarga dari Firebase."""
    ref = db.reference("family")
    family_data = ref.get()
    return {"family": family_data} if family_data else {"family": []}

def save_data(data):
    """Menyimpan data keluarga ke Firebase."""
    ref = db.reference("family")
    ref.set(data["family"])

def calculate_relationship(family, member_id):
    """Menghitung hubungan antara anggota keluarga."""
    relationships = {}
    id_to_member = {member["id"]: member for member in family}

    for member in family:
        if member["id"] == member_id:
            continue

        parent1_id = member.get("parent1_id")
        parent2_id = member.get("parent2_id")
        member_parents = (parent1_id, parent2_id)

        # Hubungan logis
        if member_id in member_parents:
            relationships[member["id"]] = "Anak"
        elif any(
            id_to_member.get(parent_id, {}).get("parent1_id") == member_id
            for parent_id in member_parents if parent_id
        ):
            relationships[member["id"]] = "Cucu"
        elif member_id in (
            id_to_member.get(parent1_id, {}).get("parent1_id"),
            id_to_member.get(parent1_id, {}).get("parent2_id"),
        ):
            relationships[member["id"]] = "Keponakan"
        elif parent1_id and id_to_member.get(parent1_id, {}).get("parent1_id") == id_to_member.get(member_id, {}).get("parent1_id"):
            relationships[member["id"]] = "Saudara"

    return relationships

def generate_family_tree(family):
    """Menghasilkan URL PNG untuk silsilah keluarga dengan gaya tambahan menggunakan QuickChart."""

    # Definisi warna dengan skema yang mencerminkan hierarki generasi
    colors = {
        'background': '#ffffff',
        'grandparent_fill': '#FFE0B2',    # Orange muda untuk kakek/nenek
        'grandparent_border': '#FB8C00',   # Orange tua untuk border kakek/nenek
        'parent_fill': '#C8E6C9',          # Hijau muda untuk orang tua
        'parent_border': '#43A047',        # Hijau tua untuk border orang tua
        'self_fill': '#E3F2FD',           # Biru muda untuk diri sendiri
        'self_border': '#1E88E5',         # Biru tua untuk border diri sendiri
        'sibling_fill': '#F3E5F5',        # Ungu muda untuk saudara
        'sibling_border': '#8E24AA',      # Ungu tua untuk border saudara
        'cousin_fill': '#FFCDD2',         # Merah muda untuk sepupu
        'cousin_border': '#E53935',       # Merah tua untuk border sepupu
        'edge': '#546E7A',                # Abu-abu gelap untuk garis penghubung
        'text': '#37474F'                 # Abu-abu sangat gelap untuk teks
    }
    
    # Awal struktur Graphviz dengan gaya yang ditingkatkan
    dot_data = f"""
    digraph G {{
        // Pengaturan Global
        bgcolor="{colors['background']}"
        rankdir=TB
        splines=ortho
        nodesep=0.8
        ranksep=1.0
        
        // Gaya Default Node
        node [
            fontname="Arial"
            fontsize=11
            shape=rectangle
            style="rounded,filled"
            penwidth=2.0
            margin="0.3,0.2"
            height=0.6
            fontcolor="{colors['text']}"
        ]
        
        // Gaya Default Edge
        edge [
            color="{colors['edge']}"
            penwidth=1.5
            arrowsize=0.8
            arrowhead=normal
            fontname="Arial"
            fontsize=9
            fontcolor="{colors['edge']}"
        ]
        
        // Pengaturan Rank
        rankdir=TB
        ranksep=0.8
    """
    
    # Fungsi untuk menentukan warna berdasarkan peran anggota keluarga
    def get_member_colors(anggota):
        anggota = anggota.lower()
        if anggota in ["kakek", "nenek"]:
            return colors['grandparent_fill'], colors['grandparent_border']
        elif anggota in ["bapak", "ibu", "paman", "bibi"]:
            return colors['parent_fill'], colors['parent_border']
        elif anggota == "saya":
            return colors['self_fill'], colors['self_border']
        elif anggota in ["adik", "kakak"]:
            return colors['sibling_fill'], colors['sibling_border']
        elif anggota == "sepupu":
            return colors['cousin_fill'], colors['cousin_border']
        else:
            return colors['sibling_fill'], colors['sibling_border']
    
    # Tambahkan node dengan gaya yang ditingkatkan
    for member in family:
        label = f'{member["name"]}\\n({member.get("anggota", "")})'
        fill_color, border_color = get_member_colors(member.get("anggota", ""))
        
        dot_data += f'''
        {member["id"]} [
            label="{label}"
            fillcolor="{fill_color}"
            color="{border_color}"
            shape={"rectangle"}
        ]
        '''
    
    # Tambahkan edge dengan label yang dipercantik
    for member in family:
        if member.get("parent1_id"):
            dot_data += f'{member["parent1_id"]} -> {member["id"]} [label=" ", dir=forward, minlen=2]\n'
        if member.get("parent2_id"):
            dot_data += f'{member["parent2_id"]} -> {member["id"]} [label=" ", dir=forward, minlen=2]\n'
    
    # Tambahkan pengaturan penataan tambahan
    dot_data += """
        // Pengaturan Layout Tambahan
        graph [
            pad="0.5",
            nodesep="0.5",
            ranksep="0.7"
        ]
    }
    """
    
    # Kirim ke API QuickChart
    response = requests.post(
        "https://quickchart.io/graphviz",
        json={"format": "png", "graph": dot_data}
    )
    
    if response.status_code == 200:
        # Simpan file PNG secara lokal
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "styled_family_tree.png")
        with open(output_path, "wb") as f:
            f.write(response.content)
        return output_path
    else:
        raise Exception(f"Error generating image: {response.text}")

@app.route("/family", methods=["GET"])
def get_family():
    """Mengembalikan data keluarga."""
    data = load_data()
    return jsonify(data)

@app.route("/family", methods=["POST"])
def add_family_member():
    """Menambahkan anggota keluarga baru."""
    data = load_data()
    new_member = request.json

    # Validasi properti wajib
    required_fields = ["id", "name", "anggota"]
    for field in required_fields:
        if field not in new_member:
            return jsonify({"error": f"Field '{field}' is required"}), 400

    # Tambahkan properti opsional jika tidak ada
    new_member.setdefault("parent1_id", None)
    new_member.setdefault("parent2_id", None)

    data["family"].append(new_member)
    save_data(data)
    return jsonify({"message": "Member added successfully"}), 201

@app.route("/family/relationship/<int:member_id>", methods=["GET"])
def describe_relationship(member_id):
    """Menghitung dan mengembalikan hubungan keluarga untuk anggota tertentu."""
    data = load_data()["family"]
    relationships = calculate_relationship(data, member_id)
    
    if not relationships:
        return jsonify([]), 200  # Jika tidak ada hubungan ditemukan, kembalikan array kosong

    response = [
        {
            "id": related_id,
            "name": next(
                (member["name"] for member in data if member["id"] == related_id),
                "Unknown"
            ),
            "relationship": relationship,
        }
        for related_id, relationship in relationships.items()
    ]
    return jsonify(response)

@app.route("/family/tree", methods=["GET"])
def family_tree():
    """Endpoint untuk menghasilkan dan mengirim file .png silsilah keluarga."""
    try:
        # Ambil data keluarga dari Firebase
        data = load_data()["family"]

        # Hasilkan file PNG menggunakan QuickChart API
        png_path = generate_family_tree(data)
        
        # Kirim file PNG sebagai respon
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name="family_tree.png"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/family/<int:member_id>", methods=["PUT"])
def update_family_member(member_id):
    """Memperbarui data anggota keluarga berdasarkan ID."""
    data = load_data()
    updated_data = request.json

    for member in data["family"]:
        if member["id"] == member_id:
            member["name"] = updated_data.get("name", member["name"])
            member["anggota"] = updated_data.get("anggota", member["anggota"])
            member["parent1_id"] = updated_data.get("parent1_id", member["parent1_id"])
            member["parent2_id"] = updated_data.get("parent2_id", member["parent2_id"])
            save_data(data)
            return jsonify({"message": "Member updated successfully"}), 200

    return jsonify({"error": "Member not found"}), 404

@app.route("/family/<int:member_id>", methods=["DELETE"])
def delete_family_member(member_id):
    """Menghapus anggota keluarga berdasarkan ID."""
    data = load_data()
    updated_family = [member for member in data["family"] if member["id"] != member_id]

    if len(updated_family) == len(data["family"]):
        return jsonify({"error": "Member not found"}), 404

    save_data({"family": updated_family})
    return jsonify({"message": "Member deleted successfully"}), 200

@app.route("/family", methods=["OPTIONS"])
@app.route("/family/<int:member_id>", methods=["OPTIONS"])
def handle_options():
    return "", 200  

if __name__ == "__main__":
    app.run(debug=True)
