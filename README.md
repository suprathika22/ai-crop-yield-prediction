# 🌾 AI Crop Yield Prediction System

This project is an **AI-based Crop Yield Prediction and Optimization System** that helps farmers estimate crop yield and make informed agricultural decisions using historical data, soil parameters, and real-time weather information.

---

## 🚀 Features

- Crop yield prediction based on crop type, land area, soil, and location  
- Soil analysis using N, P, K, and pH values  
- Real-time weather integration using OpenWeather API  
- Rule-based irrigation recommendations  
- Crop-wise pesticide recommendations using a manually created dataset  
- Web-based dashboard with downloadable PDF reports  

---

## 🧠 Technologies Used

- **Backend:** Python, Flask  
- **Data Processing:** Pandas, NumPy  
- **Machine Learning:** Scikit-learn  
- **Database:** SQLite  
- **API:** OpenWeatherMap  
- **Frontend:** HTML, CSS  

---

## 📊 Datasets & API

- **FAOSTAT Dataset:** Historical crop yield data  
- **Soil Health Data (DAC):** Soil parameters (N, P, K, pH)  
- **pesticides.csv:** Manually created dataset for pesticide recommendations  
- **OpenWeatherMap API:** Real-time weather data  

---

## 📂 Project Structure

```text
ai-crop-yield-prediction/
│── app.py
│── data/
│   ├── crop_yield.csv
│   ├── pesticides.csv
│   └── .gitkeep
│── templates/
│── static/
│── database.db
│── README.md

---

🎯 Future Enhancements

Integration with IoT-based soil sensors

Advanced ML models for improved accuracy

Mobile application support

Satellite data integration
