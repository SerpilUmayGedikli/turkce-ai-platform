"""Beceri sözlüğü: ilan ve CV'de aynı beceriyi farklı yazılışlarla (Türkçe/İngilizce) tanır.

ATS (aday takip sistemleri) çoğunlukla anahtar kelime eşleştirir. Bu yüzden ilanın istediği
becerinin CV'de *aynı adla* geçmesi önemlidir: "makine öğrenmesi" yazan CV, "machine learning"
arayan bir ATS'de kaçabilir.

Kural: "*" ile biten takma ad önek eşleşmesidir (Türkçe ekler için: "analiz*" -> "analizi",
"analizlerde"). Diğerleri tam kelime olarak aranır. Karşılaştırma tr_katla ile yapılır
(I/İ/ı/i farkı yok sayılır).
"""

from __future__ import annotations

import re
from functools import lru_cache

from ..veritabani.sorgu import tr_katla

# kanonik ad -> takma adlar (kanonik ad da otomatik olarak takma addır)
SOZLUK: dict[str, list[str]] = {
    # Programlama dilleri
    "Python": ["python"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js", "ecmascript"],
    "TypeScript": ["typescript", "ts"],
    "C#": ["c#", "csharp", "c sharp"],
    "C++": ["c++", "cpp"],
    "Go": ["golang"],
    "Rust": ["rust"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "PHP": ["php"],
    "R": ["r programlama", "r dili", "r language"],
    "MATLAB": ["matlab"],
    "SQL": ["sql", "t-sql", "pl/sql", "tsql"],
    "Bash": ["bash", "shell script*", "kabuk betik*"],
    # Veri ve ML
    "Makine Öğrenmesi": ["machine learning", "makine öğrenme*", "makine öğrenimi", "ml"],
    "Derin Öğrenme": ["deep learning", "derin öğrenme*"],
    "Doğal Dil İşleme": ["nlp", "natural language processing", "doğal dil işleme"],
    "Bilgisayarlı Görü": ["computer vision", "bilgisayarlı görü", "görüntü işleme", "image processing"],
    "Büyük Dil Modelleri": ["llm*", "large language model*", "büyük dil model*", "generative ai",
                            "üretken yapay zeka", "genai"],
    "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    "Prompt Mühendisliği": ["prompt engineering", "prompt mühendisliği"],
    "Yapay Zeka": ["artificial intelligence", "yapay zeka", "yapay zekâ"],
    "Veri Analizi": ["data analysis", "data analytics", "veri analiz*", "veri analitiği"],
    "Veri Bilimi": ["data science", "veri bilim*"],
    "Veri Mühendisliği": ["data engineering", "veri mühendisliği"],
    "İstatistik": ["statistics", "istatistik*"],
    "Veri Görselleştirme": ["data visualization", "veri görselleştirme"],
    "ETL": ["etl", "elt", "veri hattı", "data pipeline*"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch", "torch"],
    "Keras": ["keras"],
    "Hugging Face": ["hugging face", "huggingface", "transformers"],
    "LangChain": ["langchain"],
    "LangGraph": ["langgraph"],
    "MLOps": ["mlops", "ml ops"],
    "MLflow": ["mlflow"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "Hadoop": ["hadoop"],
    "Kafka": ["kafka"],
    "Airflow": ["airflow"],
    "dbt": ["dbt"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Excel": ["excel", "ms excel", "microsoft excel"],
    "Looker": ["looker"],
    "A/B Testi": ["a/b test*", "ab test*"],
    # Veritabanı
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "elastic search", "opensearch"],
    "Oracle": ["oracle"],
    "SQL Server": ["sql server", "mssql"],
    "Vektör Veritabanı": ["vector database*", "vektör veritaban*", "pgvector", "pinecone", "qdrant",
                          "weaviate", "faiss", "chroma"],
    "BigQuery": ["bigquery"],
    "Snowflake": ["snowflake"],
    # Web ve yazılım
    "React": ["react", "react.js", "reactjs"],
    "Vue": ["vue", "vue.js", "vuejs"],
    "Angular": ["angular"],
    "Node.js": ["node.js", "nodejs"],
    "Next.js": ["next.js", "nextjs"],
    "HTML/CSS": ["html", "css", "html5", "css3"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Spring": ["spring boot", "spring framework"],
    ".NET": [".net", "dotnet", "asp.net", ".net core"],
    "REST API": ["restful", "rest api", "rest servis*", "web servis*", "web service*"],
    "GraphQL": ["graphql"],
    "Mikroservis": ["microservice*", "mikroservis*"],
    "Nesne Yönelimli Programlama": ["oop", "object oriented", "object-oriented",
                                    "nesne yönelimli", "nesneye yönelik"],
    "Tasarım Desenleri": ["design pattern*", "tasarım desen*", "tasarım kalıp*"],
    "Birim Testi": ["unit test*", "birim test*", "pytest", "junit", "tdd"],
    "Git": ["git", "github", "gitlab", "bitbucket"],
    # Bulut ve DevOps
    "AWS": ["aws", "amazon web services", "sagemaker", "aws lambda", "ec2"],
    "Azure": ["azure"],
    "Google Cloud": ["gcp", "google cloud", "vertex ai"],
    "Docker": ["docker", "container*", "konteyner*"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform"],
    "CI/CD": ["ci/cd", "cicd", "jenkins", "github actions", "gitlab ci", "sürekli entegrasyon"],
    "Linux": ["linux", "unix"],
    # Mühendislik (genel)
    "AutoCAD": ["autocad"],
    "SolidWorks": ["solidworks"],
    "SAP": ["sap"],
    "PLC": ["plc"],
    "Simulink": ["simulink"],
    # Yönetim ve süreç
    "Agile": ["agile", "çevik"],
    "Scrum": ["scrum"],
    "Jira": ["jira"],
    "Proje Yönetimi": ["project management", "proje yönetim*"],
    "Ürün Yönetimi": ["product management", "ürün yönetim*"],
    # Davranışsal
    "Takım Çalışması": ["teamwork", "team player", "takım çalışma*", "ekip çalışma*"],
    "İletişim Becerisi": ["communication skill*", "iletişim beceri*", "iletişim yeteneği"],
    "Problem Çözme": ["problem solving", "problem çözme", "analitik düşünme", "analytical thinking"],
    "Liderlik": ["leadership", "liderlik"],
    "İngilizce": ["english", "ingilizce"],
    "Almanca": ["german", "almanca"],
}


def _desen(takma: str) -> str:
    onek = takma.endswith("*")
    govde = re.escape(tr_katla(takma.rstrip("*")))
    sag = r"[\wçğöşü]*" if onek else r"(?![\wçğöşü+#])"
    return rf"(?<![\wçğöşü.#+]){govde}{sag}"


@lru_cache(maxsize=1)
def _derlenmis() -> list[tuple[str, re.Pattern]]:
    sonuc = []
    for kanonik, takmalar in SOZLUK.items():
        hepsi = list(dict.fromkeys([kanonik.lower(), *takmalar]))
        sonuc.append((kanonik, re.compile("|".join(_desen(t) for t in hepsi))))
    return sonuc


def bul(metin: str) -> set[str]:
    """Metinde geçen becerilerin kanonik adlarını döndürür."""
    katli = tr_katla(metin)
    return {kanonik for kanonik, desen in _derlenmis() if desen.search(katli)}


# Alt beceri üst beceriyi ima eder: scikit-learn ile model geliştiren biri makine öğrenmesi
# yapmıştır. CV'de üst beceri adıyla geçmese bile ilanın terimiyle yazılabilir (uydurma sayılmaz).
IMA: dict[str, set[str]] = {
    "Makine Öğrenmesi": {"scikit-learn", "TensorFlow", "PyTorch", "Keras", "Derin Öğrenme",
                         "Doğal Dil İşleme", "Bilgisayarlı Görü", "MLflow", "MLOps"},
    "Derin Öğrenme": {"TensorFlow", "PyTorch", "Keras"},
    "Doğal Dil İşleme": {"Hugging Face", "Büyük Dil Modelleri", "RAG"},
    "Yapay Zeka": {"Makine Öğrenmesi", "Derin Öğrenme", "Büyük Dil Modelleri"},
    "Veri Analizi": {"Pandas", "Power BI", "Tableau", "Looker", "Veri Bilimi"},
    "Veri Görselleştirme": {"Power BI", "Tableau", "Looker"},
    "SQL": {"PostgreSQL", "MySQL", "SQL Server", "Oracle", "BigQuery", "Snowflake"},
    "Git": {"CI/CD"},
    "Agile": {"Scrum"},
}


def genislet(beceri_kumesi: set[str]) -> set[str]:
    """Kümeye, içindeki becerilerin ima ettiği üst becerileri ekler (zincirleme)."""
    sonuc = set(beceri_kumesi)
    degisti = True
    while degisti:
        yeni = {ust for ust, altlar in IMA.items() if ust not in sonuc and altlar & sonuc}
        sonuc |= yeni
        degisti = bool(yeni)
    return sonuc
