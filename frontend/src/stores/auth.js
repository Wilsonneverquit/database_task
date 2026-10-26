import { defineStore } from 'pinia'
import { api, setToken } from '@/api'
import { ACTION_ROLES, BLOCK_ROLES, PAGE_ROLES, hasAny } from '@/constants/permissions'

const USER_KEY = 'risk_alert_user'

function loadUser() {
  try { return JSON.parse(localStorage.getItem(USER_KEY)) } catch { return null }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: loadUser() }),
  getters: {
    loggedIn: (s) => !!s.user,
    roles: (s) => s.user?.roles || [],
  },
  actions: {
    async login(username, password) {
      const { token, user } = await api.login({ username, password })
      setToken(token)
      this.user = user
      try { localStorage.setItem(USER_KEY, JSON.stringify(user)) } catch { /* 忽略 */ }
    },
    logout() {
      setToken(null)
      this.user = null
      try { localStorage.removeItem(USER_KEY) } catch { /* 忽略 */ }
    },
    canPage(page) { return hasAny(this.roles, PAGE_ROLES[page] || []) },
    can(action) { return hasAny(this.roles, ACTION_ROLES[action] || []) },
    canBlock(block) { return hasAny(this.roles, BLOCK_ROLES[block] || []) },
  },
})
