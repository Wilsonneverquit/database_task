// 角色权限矩阵，依据《前端交接文档》第四节（页面"给谁看"）与第十节（权限与脱敏）、《项目拟定实施方案》2.1。
// 规则：没有权限的菜单与按钮直接不显示（不是禁用）。教师只读，任何写操作都不给。

// 页面可见性
export const PAGE_ROLES = {
  overview: ['R_ANALYST', 'R_DATA', 'R_FEATURE', 'R_ADMIN', 'R_TEACHER'],
  risk: ['R_ANALYST', 'R_TEACHER'],
  clues: ['R_ANALYST', 'R_TEACHER'],
  features: ['R_FEATURE', 'R_TEACHER'],
  ops: ['R_FEATURE', 'R_ADMIN', 'R_TEACHER'],
  eval: ['R_TEACHER'],
  audit: ['R_ADMIN', 'R_TEACHER'],
  admin: ['R_ADMIN'],
  cases: ['R_FEATURE', 'R_TEACHER'],
}

// 写操作
export const ACTION_ROLES = {
  'clue.status': ['R_ANALYST'],
  'clue.feedback': ['R_ANALYST'],
  'feature.status': ['R_FEATURE'],
  'version.publish': ['R_FEATURE'],
  'weight.recalc': ['R_FEATURE'],
  'batch.create': ['R_FEATURE', 'R_ADMIN'],
  'batch.run': ['R_FEATURE', 'R_ADMIN'],
  'param.update': ['R_ADMIN'],
}

// 概览页内各区块（管理员"不直接看案件与线索"，数据管理员看不到线索与评估）
export const BLOCK_ROLES = {
  'overview.clues': ['R_ANALYST', 'R_TEACHER'],
  'overview.risk': ['R_ANALYST', 'R_TEACHER'],
  'overview.eval': ['R_TEACHER'],
}

export function hasAny(userRoles, allowed) {
  return (userRoles || []).some((r) => allowed.includes(r))
}
