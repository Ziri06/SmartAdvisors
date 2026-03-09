import React, { useState, useEffect } from 'react';
import Layout from './components/Layout';
import WelcomePage from './components/WelcomePage';
import UploadScreen from './components/UploadScreen';
import TranscriptReview from './components/TranscriptReview';
import PreferenceForm, { Preferences } from './components/PreferenceForm';
import RecommendationDashboard from './components/RecommendationDashboard';

// Use localhost for local development
const API_URL = 'http://127.0.0.1:8000';

// link to run locally: http://localhost:5173/

interface ApiRecommendationResponse {
  success: boolean;
  recommendations: any[];
  electiveRecommendations?: any[];
  stats?: any;
}

function App() {
  const [step, setStep] = useState<number>(0); 
  const [file, setFile] = useState<File | null>(null);
  const [department, setDepartment] = useState<string>('CE'); 
  const [completedCourses, setCompletedCourses] = useState<string[]>([]); 
  const [apiData, setApiData] = useState<ApiRecommendationResponse | null>(null);
  const [userPrefs, setUserPrefs] = useState<Preferences | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [step]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUploadAndParse = async () => {
    if (!file) return;
    setIsLoading(true);

    const formData = new FormData();
    formData.append('transcript', file);

    try {
      const response = await fetch(`${API_URL}/api/parse-transcript`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      
      if (response.ok && data.courses) {
        setCompletedCourses(data.courses);
        setStep(2); 
      } else {
        alert("Error parsing transcript: " + (data.error || "Unknown error"));
      }
    } catch (error) {
      console.error("Parse error:", error);
      alert("Could not connect to server. Is the backend running?");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerate = async (preferences: Preferences) => {
    setUserPrefs(preferences);
    setIsLoading(true);

    const formData = new FormData();
    formData.append('completed_courses', JSON.stringify(completedCourses));
    formData.append('department', department);
    formData.append('preferences', JSON.stringify(preferences));

    try {
      const response = await fetch(`${API_URL}/api/recommendations`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (response.ok) {
        setApiData(data);
        setStep(4);
      } else {
        alert("Error: " + (data.error || "Unknown error occurred"));
      }
    } catch (error) {
      alert("Could not connect to server.");
    } finally {
      setIsLoading(false);
    }
  };

  if (step === 0) return <Layout onLogoClick={() => setStep(0)}><WelcomePage onGetStarted={() => setStep(1)} /></Layout>;
  if (step === 1) return <Layout onLogoClick={() => setStep(0)}><UploadScreen file={file} department={department} onFileChange={handleFileChange} setDepartment={setDepartment} onNext={handleUploadAndParse} onBack={() => setStep(0)} /></Layout>;
  if (step === 2) return <Layout onLogoClick={() => setStep(0)}><TranscriptReview courses={completedCourses} onNext={() => setStep(3)} onBack={() => setStep(1)} /></Layout>;
  if (step === 3) return <Layout onLogoClick={() => setStep(0)}><PreferenceForm onGenerateSchedule={handleGenerate} isLoading={isLoading} onBack={() => setStep(2)} /></Layout>;
  if (step === 4 && apiData && userPrefs) return <Layout onLogoClick={() => setStep(0)}><RecommendationDashboard userData={{ preferences: userPrefs, recommendations: apiData.recommendations, electiveRecommendations: apiData.electiveRecommendations || [], stats: apiData.stats }} onBack={() => setStep(3)} /></Layout>;

  return <div>Loading...</div>;
}

export default App;