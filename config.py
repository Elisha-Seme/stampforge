import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'stampforge-secret-key-change-in-production')
    DATABASE_PATH = os.path.join(BASE_DIR, 'stampforge.db')

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    GENERATED_FOLDER = os.path.join(BASE_DIR, 'static', 'generated')
    FONTS_FOLDER = os.path.join(BASE_DIR, 'static', 'fonts')

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload

    ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_PDF_EXTENSIONS = {'pdf'}
    ALLOWED_CSV_EXTENSIONS = {'csv'}

    # Stamp DPI
    STAMP_DPI = 300

    # Stamp sizes in pixels at 300 DPI
    STAMP_SIZES = {
        'small':  (300, 300),
        'medium': (500, 500),
        'large':  (750, 750),
    }

    RECT_STAMP_SIZES = {
        'small':  (400, 200),
        'medium': (600, 300),
        'large':  (900, 450),
    }

    # Verification base URL (update to your domain in production)
    VERIFICATION_BASE_URL = 'http://localhost:5000/verify'
