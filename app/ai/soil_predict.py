import os
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(BASE_DIR, "soil_classifier_model.h5")

model = load_model(model_path)

# Class labels (VERY IMPORTANT - same order as training)
classes = [
    "Alluvial Soil",
    "Arid Soil",
    "Black Soil",
    "Laterite Soil",
    "Mountain Soil",
    "Red Soil",
    "Yellow Soil"
]

def predict_soil(img_path):
    img = image.load_img(img_path, target_size=(224, 224))  # adjust if needed
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) / 255.0

    prediction = model.predict(img_array)
    class_index = np.argmax(prediction)

    soil_type = classes[class_index]
    confidence = float(np.max(prediction)) * 100

    return soil_type, round(confidence, 2)