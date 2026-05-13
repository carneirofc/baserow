import { Registerable } from '@baserow/modules/core/registry'

export class ServiceType extends Registerable {
  get name() {
    throw new Error('Must be set on the type.')
  }

  /**
   * The integration type necessary to access this service.
   */
  get integrationType() {
    return null
  }

  /**
   * The form component to edit this service.
   */
  get formComponent() {
    return null
  }

  get icon() {
    return 'iconoir-question-mark'
  }

  /**
   * Allow to hook into default values for this service type.
   * @param {object} service the service being edited.
   * @param {object} values the current default values for the service form.
   * @returns an object containing values updated with the default values.
   */
  getDefaultValues(service, values) {
    return values
  }

  /**
   * Whether the service is valid.
   * @param service - The service object.
   * @returns {String} - The error message
   */
  getErrorMessage({ service, workspace = null }) {
    const deactivatedReason =
      workspace && this.isDeactivatedReason({ workspace })
    if (deactivatedReason) {
      return deactivatedReason
    }

    return null
  }

  /**
   * Whether the service is valid.
   * @param service - The service object.
   * @returns {boolean} - If the service is valid.
   */
  isInError(params) {
    return Boolean(this.getErrorMessage(params))
  }

  /**
   * Should return a JSON schema of the data returned by this service.
   */
  getDataSchema(applicationContext, service) {
    throw new Error('Must be set on the type.')
  }

  /**
   * Returns sample data for the given service.
   */
  getSampleData(service) {
    return service.sample_data || null
  }

  /**
   * A hook called prior to an update to modify the new values
   * before they get persisted in the API.
   */
  beforeUpdate(newValues, oldValues) {
    return newValues
  }

  /**
   * Returns a description of the given service
   */
  getDescription(service, application) {
    return this.name
  }

  /**
   * Allow to customize way data are accessed from service
   */
  prepareValuePath(service, path) {
    return path
  }

  /**
   * Whether the service returns a collection of records.
   */
  get returnsList() {
    return false
  }

  isDeactivatedReason({ workspace }) {
    return null
  }

  isDeactivated({ workspace }) {
    return !!this.isDeactivatedReason({ workspace })
  }

  getDeactivatedClickModal({ workspace }) {
    return null
  }

  getOrder() {
    return 0
  }
}

export const DataSourceServiceTypeMixin = (Base) =>
  class extends Base {
    isDataSource = true

    /**
     * In a service which returns a list, this method is used to
     * return the name of the given record.
     */
    getRecordName(service, record) {
      throw new Error('Must be set on the type.')
    }

    /**
     * In a service which returns a list, this method is used to
     * return the id of the given record.
     */
    getIdProperty(service, record) {
      throw new Error('Must be set on the type.')
    }

    /**
     * Convert record-name endpoint keys back to the value type used by this service.
     */
    parseRecordId(value) {
      return parseInt(value)
    }

    /**
     * Returns the JSON-schema type used by this service's record identifiers.
     */
    getRecordIdDataType(service) {
      return 'number'
    }

    /**
     * Some list services use record identifiers that can be displayed without
     * fetching the record name endpoint. Return null to fall back to the endpoint.
     */
    getRecordNameFromId(service, recordId) {
      return null
    }

    /**
     * The maximum number of records that can be returned by this service
     */
    getMaxResultLimit(service) {
      return null
    }

    /**
     * Whether this list data source supports frontend paging controls.
     */
    get supportsPagination() {
      return this.returnsList
    }

    /**
     * This method can be used to process service data
     * in the frontend when displaying raw data
     * is not enough.
     */
    getResult(service, data) {
      return null
    }
  }

export const WorkflowActionServiceTypeMixin = (Base) =>
  class extends Base {
    isWorkflowAction = true
  }

export const TriggerServiceTypeMixin = (Base) =>
  class extends Base {
    isTrigger = true

    canBeImmediatelyDispatched(service) {
      return false
    }
  }
