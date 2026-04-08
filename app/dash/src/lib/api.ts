import axios from 'axios'

// Uses Vite dev-server proxy (added later) so we can call relative paths.
export const guardianApi = axios.create({
  withCredentials: true,
})

