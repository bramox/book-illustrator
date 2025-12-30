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
      setResponse("The book has been successfully generated and is being downloaded.")
    } catch (err) {
      setError(err.response?.data || 'There was an error sending data')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="App">
      <h1>Picture book generator</h1>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '600px', margin: '0 auto' }}>
        <input
          type="text"
          name="title"
          placeholder="Book title"
          value={bookData.title}
          onChange={handleChange}
        />
        <input
          type="text"
          name="author"
          placeholder="Author"
          value={bookData.author}
          onChange={handleChange}
        />
        <textarea
          name="text"
          placeholder="Book text (required)"
          value={bookData.text}
          onChange={handleChange}
          required
          rows={10}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Processing...' : 'Generate'}
        </button>
      </form>

      {error && (
        <div style={{ color: 'red', marginTop: '20px' }}>
          <h3>Error:</h3>
          <pre>{JSON.stringify(error, null, 2)}</pre>
        </div>
      )}

      {response && <p>{response}</p>}
    </div>
  )
}

export default App
