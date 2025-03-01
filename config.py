import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'mishek001'
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:@localhost:3307/digiTTrain2'
    SQLALCHEMY_TRACK_MODIFICATIONS = False