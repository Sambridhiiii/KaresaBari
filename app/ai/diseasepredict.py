import tensorflow as tf
import numpy as np
from tensorflow.keras.preprocessing import image
import os

# ---------------------------------
# LOAD MODEL
# ---------------------------------
MODEL_PATH = os.path.join(os.path.dirname(__file__), "best_model.h5")
model = tf.keras.models.load_model(MODEL_PATH)

# ---------------------------------
# CLASS LABELS (Must match model output)
# ---------------------------------
classes = [
    "chili_bacterial_spot", "chili_cercospora_leaf_spot", "chili_curl_virus",
    "chili_healthy_leaf", "chili_nutrition_deficiency", "chili_white_spot",
    "corn_maize_healthy", "corn_maize_leaf_blight", "corn_maize_streak_virus",
    "potato_fungi", "potato_healthy", "potato_nematode",
    "spanish_malabar_spinach_disease", "spanish_malabar_spinach_healthy",
    "spanish_red_spinach_disease", "spanish_red_spinach_healthy",
    "spanish_water_spinach_disease", "spanish_water_spinach_healthy",
    "tomato_tomato__bacterial_spot", "tomato_tomato__early_blight",
    "tomato_tomato__late_blight", "tomato_tomato__leaf_mold",
    "tomato_tomato__spider_mites_two-spotted_spider_mite",
    "tomato_tomato__target_spot", "tomato_tomato__tomato_mosaic_virus",
    "tomato_tomato__tomato_yellow_leaf_curl_virus", "tomato_tomato_healthy"
]

# ---------------------------------
# PREDICTION FUNCTION
# ---------------------------------
def predict_disease(img_path):
    img = image.load_img(img_path, target_size=(224, 224))
    img_array = image.img_to_array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    prediction = model.predict(img_array)
    class_index = np.argmax(prediction)
    
    # SAFETY: Prevent IndexError if model predicts out of list bounds
    if class_index >= len(classes):
        class_index = len(classes) - 1 

    predicted_class = classes[class_index]
    confidence = float(np.max(prediction)) * 100

    parts = predicted_class.split("_")
    plant_raw = parts[0].title()
    disease_raw = "_".join(parts[1:]).replace("__", " ").replace("_", " ").title()

    # Dynamic Data based on infection status
    if "Healthy" in disease_raw:
        res = {
            "severity": 1,
            "analysis_note": "No pathogens detected. Plant showing optimal vigor.",
            "pattern": "Uniform leaf color and texture.",
            "immediate_action": "No intervention needed.",
            "treatment": "Maintain regular watering and organic fertilization.",
            "prevention": "Continue monitoring and ensure proper spacing."
        }
    else:
        res = {
            "severity": 4 if confidence > 80 else 3,
            "analysis_note": f"Visible symptoms of {disease_raw} detected. Risk of spread is moderate.",
            "pattern": "Irregular lesions and discoloration on primary leaves.",
            "immediate_action": "Isolate the plant and prune affected foliage.",
            "treatment": f"Apply appropriate treatment for {disease_raw}.",
            "prevention": "Sterilize tools and improve air circulation."
        }

    return {
        "plant": plant_raw,
        "disease": disease_raw,
        "confidence": round(confidence, 2),
        "location": "Bagmati, Nepal",
        **res
    }