import pandas as pd
from docx import Document
from docx2pdf import convert
from PyPDF2 import PdfMerger
import os
import re
import shutil
import traceback
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename
from flask_cors import CORS
import time
import zipfile
import json
import hashlib
from functools import wraps # Vamos precisar novamente para os decorators

app = Flask(__name__, template_folder='templates')
CORS(app,
     supports_credentials=True,
     origins=["http://127.0.0.1:5000", "http://localhost:5000"]
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'temp_uploads_web')
GENERATED_CERTIFICATES_FOLDER = os.path.join(BASE_DIR, 'generated_certificates_web')
USERS_DB_PATH = os.path.join(BASE_DIR, 'users_db.json') # Caminho para o arquivo da base de dados de usuários

# Garante que as pastas existam
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_CERTIFICATES_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GENERATED_CERTIFICATES_FOLDER'] = GENERATED_CERTIFICATES_FOLDER
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60) # Tempo de vida da sessão (ex: para tokens)

# --- Base de Dados de Utilizadores (Persistida em JSON com Senhas HASHED) ---
def load_users_db():
    """Carrega a base de dados de usuários do arquivo JSON."""
    if os.path.exists(USERS_DB_PATH):
        with open(USERS_DB_PATH, 'r') as f:
            return json.load(f)
    return {}

def save_users_db(db):
    """Salva a base de dados de usuários no arquivo JSON."""
    with open(USERS_DB_PATH, 'w') as f:
        json.dump(db, f, indent=4)

# Carrega o DB ao iniciar a aplicação
users_db = load_users_db()

# Adiciona o usuário 'danilo' padrão se o DB estiver vazio ou 'danilo' não existir
if "danilo" not in users_db:
    danilo_password_hash = hashlib.sha256("@danilo30!".encode('utf-8')).hexdigest()
    users_db["danilo"] = {
        "password_hash": danilo_password_hash,
        "role": "admin"
    }
    save_users_db(users_db)
    print("INFO: Usuário 'danilo' (admin) padrão criado/verificado com senha '@danilo30!' (hashed).")

# ---------------------------------------------------------------------

# --- Decoradores de Autenticação e Autorização ---
def require_auth(f):
    """Decorator para exigir autenticação baseada em token simples (simulado)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            print("INFO: Autenticação falhou: Cabeçalho 'Authorization' ausente ou mal formatado.")
            return jsonify({"error": "Autenticação requerida. Token de acesso ausente ou inválido."}), 401

        token = auth_header.split(' ')[1]

        # Para fins desta simulação, o token é o próprio username.
        # Em um cenário real, você usaria JWTs ou sessions.
        if token in users_db:
            request.current_user = token # Adiciona o usuário autenticado ao objeto request
            request.current_user_role = users_db[token].get("role", "user") # Adiciona a role
            return f(*args, **kwargs)
        else:
            print(f"INFO: Autenticação falhou: Token '{token}' inválido.")
            return jsonify({"error": "Token de acesso inválido ou expirado."}), 401
    return decorated_function

def require_role(role):
    """Decorator para exigir uma role específica."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'current_user') or not hasattr(request, 'current_user_role'):
                print("ERRO: Erro interno de autenticação - usuário ou role não definidos após require_auth.")
                return jsonify({"error": "Erro de autenticação interno: usuário não definido."}), 500

            if request.current_user_role == role:
                return f(*args, **kwargs)
            else:
                print(f"INFO: Acesso negado para '{request.current_user}'. Requer role: '{role}', mas é '{request.current_user_role}'.")
                return jsonify({"error": f"Acesso negado. Requer role: '{role}'."}), 403
        return decorated_function
    return decorator

# --- Rotas da Aplicação ---
@app.route('/')
def index():
    """Renderiza a página principal do gerador."""
    return render_template('gerador_web.html')

# --- Funções de Processamento de Documentos (mantidas as mesmas) ---
def process_document_tags(document_obj, data_row):
    """
    Processa as tags de substituição em um documento Word.
    Substitui tags no formato {TAG} pelos valores correspondentes na data_row.
    Mantém a formatação original do parágrafo/run.
    """
    for paragraph in document_obj.paragraphs:
        full_paragraph_text = paragraph.text
        if '{' in full_paragraph_text and '}' in full_paragraph_text:
            original_runs = list(paragraph.runs)
            replaced_text = replace_all_tags_in_text(full_paragraph_text, data_row)
            if replaced_text != full_paragraph_text:
                apply_formatting_runs(paragraph, original_runs, replaced_text)

    for table in document_obj.tables:
        for row_table in table.rows:
            for cell in row_table.cells:
                for paragraph_in_cell in cell.paragraphs:
                    full_cell_text = paragraph_in_cell.text
                    if '{' in full_cell_text and '}' in full_cell_text:
                        original_runs_cell = list(paragraph_in_cell.runs)
                        replaced_cell_text = replace_all_tags_in_text(full_cell_text, data_row)
                        if replaced_cell_text != full_cell_text:
                            apply_formatting_runs(paragraph_in_cell, original_runs_cell, replaced_cell_text)

def replace_all_tags_in_text(text_content, data_row_normalized):
    """
    Encontra e substitui todas as tags {TAG} em um texto.
    Normaliza os nomes das tags para buscar na data_row (minúsculas, sem espaços extras).
    """
    tags_found_in_word = re.findall(r'\{(.*?)\}', text_content)
    for tag_content in tags_found_in_word:
        normalized_tag_from_word = tag_content.strip().lower()
        replacement_value = str(data_row_normalized.get(normalized_tag_from_word, f'{{{tag_content}}}'))
        text_content = text_content.replace(f'{{{tag_content}}}', replacement_value)
    return text_content

def apply_formatting_runs(paragraph, original_runs, replaced_text):
    """
    Aplica a formatação do primeiro run original a um novo run que contém o texto substituído.
    """
    paragraph.clear()
    if original_runs:
        first_run_original = original_runs[0]
        new_run = paragraph.add_run(replaced_text)
        new_run.bold = first_run_original.bold
        new_run.italic = first_run_original.italic
        new_run.underline = first_run_original.underline
        if first_run_original.font.name:
            new_run.font.name = first_run_original.font.name
        if first_run_original.font.size:
            new_run.font.size = first_run_original.font.size
        if first_run_original.font.color and first_run_original.font.color.rgb:
            new_run.font.color.rgb = first_run_original.font.color.rgb
    else:
        paragraph.add_run(replaced_text)

def create_zip_from_folder(folder_path, zip_path):
    """Cria um arquivo ZIP a partir do conteúdo de uma pasta."""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file_item in files:
                file_path_item = os.path.join(root, file_item)
                archive_name = os.path.relpath(file_path_item, folder_path)
                zipf.write(file_path_item, archive_name)
    print(f"INFO: Ficheiro ZIP criado em: {zip_path}")

# --- Endpoints de Gestão de Utilizadores ---
@app.route('/api/users', methods=['GET'])
@require_auth
@require_role('admin') # Apenas admins podem ver a lista de usuários
def get_users_api():
    """Retorna a lista de usuários (sem senhas)."""
    user_list = []
    for user, data in users_db.items():
        user_list.append({
            "username": user,
            "role": data.get("role", "user")
            # NUNCA retornar password_hash aqui!
        })
    return jsonify(user_list), 200

@app.route('/api/users/create', methods=['POST'])
@require_auth
@require_role('admin') # Apenas admins podem criar usuários
def create_user_api():
    """Cria um novo usuário no sistema."""
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Nome de utilizador e senha são obrigatórios."}), 400

    username = data['username'].strip()
    password = data['password']
    role = data.get('role', 'user').strip().lower()

    if not username or not password:
        return jsonify({"error": "Nome de utilizador e senha não podem ser vazios."}), 400
    if role not in ['user', 'admin']:
        return jsonify({"error": "Role inválida. Use 'user' ou 'admin'."}), 400

    if username in users_db:
        return jsonify({"error": f"Utilizador '{username}' já existe."}), 409

    # Hash da senha antes de armazenar
    password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

    users_db[username] = {
        "password_hash": password_hash,
        "role": role
    }
    save_users_db(users_db) # Salva as alterações no arquivo
    print(f"INFO: Utilizador '{username}' (role: {role}) criado (em memória e persistido).")
    return jsonify({"message": f"Utilizador '{username}' criado com sucesso.", "username": username, "role": role}), 201

# --- Endpoint de Login ---
@app.route('/api/login', methods=['POST'])
def login_api():
    """
    Endpoint de login. Autentica o usuário e retorna um "token" (neste caso, o username
    como token).
    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Nome de utilizador e senha são obrigatórios."}), 400

    username = data['username']
    password_input = data['password']

    user_data = users_db.get(username)

    if user_data:
        # Verifica a senha hashed
        input_password_hash = hashlib.sha256(password_input.encode('utf-8')).hexdigest()
        if user_data['password_hash'] == input_password_hash:
            print(f"INFO: Tentativa de login bem-sucedida para '{username}'.")
            return jsonify(
                message="Login bem-sucedido.",
                user=username,
                role=user_data.get("role", "user"),
                token=username # Token simulado
            ), 200

    print(f"INFO: Tentativa de login falhada para o utilizador '{username}'.")
    return jsonify({"error": "Nome de utilizador ou senha inválidos."}), 401

# --- Endpoint Principal de Geração de Certificados ---
@app.route('/generate_certificates_api', methods=['POST'])
@require_auth # Este endpoint agora requer autenticação (qualquer usuário logado)
def generate_certificates_api():
    """
    Gera certificados em PDF a partir de um arquivo Excel e um template Word.
    """
    print(f"INFO: Endpoint /generate_certificates_api acedido por '{request.current_user}'.")

    if 'excelFile' not in request.files or 'templateFile' not in request.files:
        return jsonify({"error": "Arquivos Excel e Template são obrigatórios."}), 400

    excel_file = request.files['excelFile']
    template_file = request.files['templateFile']

    if excel_file.filename == '' or template_file.filename == '':
        return jsonify({"error": "Nomes de arquivo não podem ser vazios."}), 400

    request_id_suffix = request.current_user # Usa o nome de usuário autenticado
    request_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + f"_{request_id_suffix}"

    current_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], request_id)
    session_output_path = os.path.join(app.config['GENERATED_CERTIFICATES_FOLDER'], f"output_{request_id}")
    zip_staging_folder = os.path.join(session_output_path, "staging_for_zip")
    individual_docx_staging_folder = os.path.join(zip_staging_folder, "WORDs_Individuais")
    individual_pdf_staging_folder = os.path.join(zip_staging_folder, "PDFs_Individuais")

    # Garante que todas as pastas de trabalho existam
    os.makedirs(current_upload_folder, exist_ok=True)
    os.makedirs(session_output_path, exist_ok=True)
    os.makedirs(zip_staging_folder, exist_ok=True)
    os.makedirs(individual_docx_staging_folder, exist_ok=True)
    os.makedirs(individual_pdf_staging_folder, exist_ok=True)

    excel_path = os.path.join(current_upload_folder, secure_filename(excel_file.filename))
    template_path = os.path.join(current_upload_folder, secure_filename(template_file.filename))

    try:
        excel_file.save(excel_path)
        template_file.save(template_path)
    except Exception as e:
        print(f"ERRO: Falha ao salvar arquivos de upload: {e}")
        traceback.print_exc()
        shutil.rmtree(current_upload_folder, ignore_errors=True)
        return jsonify({"error": f"Erro ao salvar arquivos: {e}"}), 500

    any_processing_errors = False

    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        traceback.print_exc()
        shutil.rmtree(current_upload_folder, ignore_errors=True)
        shutil.rmtree(session_output_path, ignore_errors=True) # Limpa pastas vazias se houver erro no Excel
        return jsonify({"error": f"Erro ao ler arquivo Excel. Verifique o formato do arquivo: {e}"}), 500

    total_participants_overall = df.apply(lambda x: x.dropna().count()).sum()
    if total_participants_overall == 0:
        shutil.rmtree(current_upload_folder, ignore_errors=True)
        shutil.rmtree(session_output_path, ignore_errors=True)
        return jsonify({"message": "Nenhum participante encontrado no arquivo Excel.", "zip_file_path": None}), 200

    processed_participants_overall_count = 0

    for col_idx, column_excel_header in enumerate(df.columns):
        current_col_header_str = str(column_excel_header)
        clean_column_name_for_folder = re.sub(r'[^\w\s-]', '', current_col_header_str).strip().replace(' ', '_')
        if not clean_column_name_for_folder:
            clean_column_name_for_folder = f"Coluna_{col_idx + 1}"

        column_aggregate_staging_folder = os.path.join(zip_staging_folder, clean_column_name_for_folder)
        os.makedirs(column_aggregate_staging_folder, exist_ok=True)

        participant_names_in_column = df[column_excel_header].dropna()
        if participant_names_in_column.empty:
            continue

        pdfs_for_this_column_merger_paths = []

        for item_idx, participant_name_raw in enumerate(participant_names_in_column):
            participant_name = str(participant_name_raw).strip()
            if not participant_name:
                continue
            processed_participants_overall_count += 1

            data_for_tags = {'nome': participant_name}

            base_filename_participant = re.sub(r'[^\w\s-]', '', participant_name).strip().replace(' ', '_').replace('/', '_')
            if not base_filename_participant:
                base_filename_participant = f"Participante_{col_idx + 1}_{item_idx + 1}"
            else:
                base_filename_participant = f"{base_filename_participant}_{col_idx +1}_{item_idx + 1}"

            output_docx_name = os.path.join(individual_docx_staging_folder, f"certificado_{base_filename_participant}.docx")
            output_pdf_name = os.path.join(individual_pdf_staging_folder, f"certificado_{base_filename_participant}.pdf")

            try:
                doc = Document(template_path)
                process_document_tags(doc, data_for_tags)
                doc.save(output_docx_name)
                time.sleep(0.1)

                try:
                    convert(output_docx_name, output_pdf_name)
                    time.sleep(0.05)
                    if os.path.exists(output_pdf_name):
                        pdfs_for_this_column_merger_paths.append(output_pdf_name)
                except Exception as pdf_conversion_error:
                    print(f"ERRO conversão PDF para {participant_name}: {pdf_conversion_error}")
                    traceback.print_exc()
                    any_processing_errors = True
            except Exception as e_docx:
                print(f"ERRO DOCX para {participant_name}: {e_docx}")
                traceback.print_exc()
                any_processing_errors = True
                continue

        if pdfs_for_this_column_merger_paths:
            merger = PdfMerger()
            for pdf_path in pdfs_for_this_column_merger_paths:
                try:
                    if os.path.exists(pdf_path):
                        merger.append(pdf_path)
                except Exception as merge_err:
                    print(f"ERRO ao adicionar PDF '{pdf_path}' ao agregador da coluna: {merge_err}")
                    traceback.print_exc()
                    any_processing_errors = True

            if merger.inputs:
                merged_filename = f"TODOS_CERTIFICADOS_{clean_column_name_for_folder}.pdf"
                final_column_merged_path = os.path.join(column_aggregate_staging_folder, merged_filename)
                try:
                    merger.write(final_column_merged_path)
                    merger.close()
                except Exception as e_merge:
                    print(f"ERRO ao salvar PDF agregado da coluna '{clean_column_name_for_folder}': {e_merge}")
                    traceback.print_exc()
                    any_processing_errors = True
            else:
                merger.close()

    zip_filename = "Certificados_Gerados.zip"
    zip_file_full_path = os.path.join(session_output_path, zip_filename)

    try:
        create_zip_from_folder(zip_staging_folder, zip_file_full_path)
        shutil.rmtree(zip_staging_folder, ignore_errors=True)
    except Exception as e_zip:
        print(f"ERRO ao criar ou limpar o ficheiro ZIP/pasta staging: {e_zip}")
        traceback.print_exc()
        any_processing_errors = True
        return jsonify({"error": f"Erro ao criar ficheiro ZIP: {e_zip}", "zip_file_path": None}), 500

    try:
        shutil.rmtree(current_upload_folder, ignore_errors=True)
    except Exception as e_clean:
        print(f"ERRO ao remover pasta de upload temporária '{current_upload_folder}': {e_clean}")
        traceback.print_exc()

    final_message = "Certificados processados e empacotados com sucesso."
    if any_processing_errors:
        final_message += " No entanto, alguns erros ocorreram durante o processo de geração/conversão de PDFs. Verifique os logs do servidor para mais detalhes."

    zip_download_path = os.path.join(os.path.basename(session_output_path), zip_filename)
    print(f"INFO: {final_message}. Caminho do ZIP para download: {zip_download_path}")
    return jsonify({"message": final_message, "zip_file_path": zip_download_path}), 200

@app.route('/download_generated_file/<path:filepath>')
@require_auth # Este endpoint agora requer autenticação
def download_generated_file(filepath):
    """
    Permite o download de arquivos gerados, garantindo que o acesso seja restrito à pasta de certificados gerados.
    """
    print(f"INFO: Pedido de download para: '{filepath}' por '{request.current_user}'.")

    full_file_path = os.path.join(app.config['GENERATED_CERTIFICATES_FOLDER'], filepath)
    resolved_file_path = os.path.realpath(full_file_path)

    allowed_dir = os.path.realpath(app.config['GENERATED_CERTIFICATES_FOLDER'])

    if not resolved_file_path.startswith(allowed_dir):
        print(f"ERRO: Tentativa de acesso a caminho inválido (fora da pasta permitida): {resolved_file_path}")
        return "Acesso negado: caminho inválido.", 403

    if os.path.exists(resolved_file_path) and os.path.isfile(resolved_file_path):
        try:
            return send_file(resolved_file_path, as_attachment=True)
        except Exception as e_send:
            print(f"ERRO CRÍTICO em send_file para '{resolved_file_path}': {e_send}")
            traceback.print_exc()
            return "Erro interno ao tentar servir o ficheiro.", 500
    else:
        print(f"ERRO: Ficheiro não encontrado para download: {resolved_file_path}")
        return "Arquivo não encontrado.", 404

if __name__ == '__main__':
    print("INFO: Iniciando servidor Flask em http://127.0.0.1:5000 (ou outro host/porta se configurado).")
    print("AVISO: Esta aplicação usa um sistema de autenticação simplificado (username como token e senhas hashed em JSON).")
    print("NÃO use para produção sem implementar autenticação e segurança robustas (ex: JWTs, OAuth2, gerenciamento de sessão adequado).")
    #app.run(debug=True, host='0.0.0.0', port=5000)#