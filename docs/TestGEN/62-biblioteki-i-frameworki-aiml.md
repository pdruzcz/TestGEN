# **6.2.** Biblioteki i frameworki AI/ML

### **6.2.1.** Natural Language Processing (NLP)

  ---------------------------------------------------------------------------
  **Biblioteka**          **Wersja**   **Zastosowanie w TestGEN**
  ----------------------- ------------ --------------------------------------
  Transformers            4.30+        Modele BERT, GPT do analizy
  (HuggingFace)                        dokumentacji i kodu

  spaCy                   3.6+         NER, dependency parsing, text
                                       classification

  NLTK                    3.8+         Tokenization, POS tagging, text
                                       preprocessing

  LangChain               0.0.300+     LLM orchestration, prompt engineering

  Sentence Transformers   2.2+         Semantic similarity, embeddings
  ---------------------------------------------------------------------------

### **6.2.2.** Machine Learning Frameworks

  -------------------------------------------------------------------------
  **Framework**    **Wersja**   **Zastosowanie**
  ---------------- ------------ -------------------------------------------
  TensorFlow       2.13+        Deep learning models, neural networks

  PyTorch          2.0+         Custom model training, fine-tuning

  scikit-learn     1.3+         Classical ML algorithms, preprocessing

  XGBoost          2.0+         Classification, ranking models
  -------------------------------------------------------------------------

### **6.2.3.** Modele językowe wykorzystywane

**Modele bazowe (foundation models):**

- **GPT-4 / GPT-3.5-turbo (OpenAI)** - generowanie kodu testów, analiza
  semantyczna

- **CodeLlama (Meta)** - specjalizowany model do analizy i generowania
  kodu

- **BERT-base / RoBERTa** - klasyfikacja tekstu, NER w dokumentacji

- **CodeBERT (Microsoft)** - rozumienie kodu źródłowego

- **T5 / FLAN-T5** - text-to-text generation, parafrazowanie

**Fine-tuning:** Modele bazowe będą dodatkowo fine-tunowane na
domenowych danych (test cases, security vulnerabilities, code patterns)
aby zwiększyć dokładność i specjalizację.
