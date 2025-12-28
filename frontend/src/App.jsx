import { useState } from 'react'
import axios from 'axios'
import './App.css'

function App() {
  const [bookData, setBookData] = useState({
    title: '',
    author: '',
    text: ''
  })
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleChange = (e) => {
    const { name, value } = e.target
    setBookData(prev => ({
      ...prev,
      [name]: value
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResponse(null)

    try {
      const res = await axios.post('http://localhost:8000/api/books/', bookData, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'generated_book.pdf');
      document.body.appendChild(link);
      link.click();
      setBookData({ title: '', author: '', text: '' })
      setResponse("Книга успешно сгенерирована и скачивается.")
    } catch (err) {
      setError(err.response?.data || 'Произошла ошибка при отправке данных')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="App">
      <h1>Генератор иллюстрированных книг</h1>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '600px', margin: '0 auto' }}>
        <input
          type="text"
          name="title"
          placeholder="Название книги"
          value={bookData.title}
          onChange={handleChange}
        />
        <input
          type="text"
          name="author"
          placeholder="Автор"
          value={bookData.author}
          onChange={handleChange}
        />
        <textarea
          name="text"
          placeholder="Текст книги (обязательно)"
          value={bookData.text}
          onChange={handleChange}
          required
          rows={10}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Обработка...' : 'Сгенерировать'}
        </button>
      </form>

      {error && (
        <div style={{ color: 'red', marginTop: '20px' }}>
          <h3>Ошибка:</h3>
          <pre>{JSON.stringify(error, null, 2)}</pre>
        </div>
      )}

      {response && <p>{response}</p>}
    </div>
  )
}

export default App
