import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) => {
  return Object.assign(baseService(client, '/admin/audit-log/'), {
    export(searchQuery, sorts, filters) {
      const params = Object.assign({}, filters)
      if (searchQuery) {
        params.search = searchQuery
      }
      return client.get('/admin/audit-log/export/', {
        params,
        responseType: 'blob',
      })
    },
  })
}
