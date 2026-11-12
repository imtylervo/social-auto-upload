# Vue3 + Vite Project

A modern frontend project template based on Vue3, Vite, Element Plus, Pinia, Vue Router and Axios.

## 🚀 Features

- ⚡️ **Vite** - very fast build tool
- 🖖 **Vue 3** - progressive JavaScript framework
- 🎨 **Element Plus** - component library for Vue 3
- 🗂 **Vue Router** - official router (WebHash mode)
- 📦 **Pinia** - next-generation state management
- 🔗 **Axios** - HTTP client (wrapped)
- 🎯 **Sass** - CSS preprocessor
- 📁 **Standard directory layout** - pages in views, components in components
- 🔧 **Complete configuration** - includes development and production settings

## 📦 Installation

```bash
# Install dependencies
npm install

# Start the dev server
npm run dev

# Build for production
npm run build

# Preview the production build
npm run preview
```

## 📁 Project Structure

```
src/
├── api/                 # API endpoints
│   ├── index.js        # Single export point for the APIs
│   └── user.js         # User API
├── components/          # Shared components
│   └── HelloWorld.vue  # Example component
├── router/             # Router configuration
│   └── index.js        # Main router file
├── stores/             # State management
│   ├── index.js        # Pinia setup
│   └── user.js         # User state
├── styles/             # Style files
│   ├── index.scss      # Main stylesheet
│   ├── reset.scss      # Reset styles
│   └── variables.scss  # Style variables
├── utils/              # Utility functions
│   └── request.js      # HTTP request wrapper
├── views/              # Page components
│   ├── Home.vue        # Home page
│   └── About.vue       # About page
├── App.vue             # Root component
└── main.js             # Entry file
```

## 🔧 Configuration

### Environment Variables

- `.env` - shared environment variables
- `.env.development` - development environment variables
- `.env.production` - production environment variables

### Routing

The project uses Vue Router 4 in WebHash mode. The router file is `src/router/index.js`.

### State Management

State is managed with Pinia. The store files are in `src/stores/`.

### HTTP Requests

Axios is wrapped and includes:
- Request/response interceptors
- Error handling
- Automatic token header
- Uniform response format handling

Usage:
```javascript
import { http } from '@/utils/request'

// GET request
const data = await http.get('/api/users')

// POST request
const result = await http.post('/api/users', { name: 'John' })
```

### Styles

- Sass as the CSS preprocessor
- All browser default styles removed
- A full set of style variables and utility classes
- Element Plus theme customization supported

## 🎨 Component Library

The project includes Element Plus; all of its components can be used directly:

```vue
<template>
  <el-button type="primary">Button</el-button>
  <el-input v-model="input" placeholder="Enter text"></el-input>
</template>
```

## 📝 Conventions

1. **Page components** go in `src/views/`
2. **Shared components** go in `src/components/`
3. **Use the `<script setup>` syntax** for components
4. **Write styles in Sass** and follow BEM naming
5. **API requests** all go in `src/api/`
6. **State** is split by module and goes in `src/stores/`

## 🚀 Deployment

```bash
# Build for production
npm run build

# After the build, the dist directory contains all static files
# They can be deployed to any static file server
```

## 📄 License

MIT License
