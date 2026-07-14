import { TestApp } from '@baserow/test/helpers/testApp'
import nodeStore, {
  getWorkflowImmediateDispatch,
} from '@baserow/modules/automation/store/automationWorkflowNode'

describe('Automation workflow node store', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test.each([
    ['manual', true],
    ['periodic', true],
    ['http_trigger', false],
    ['local_baserow_rows_created', false],
  ])('computes immediate dispatch for %s triggers', (type, expected) => {
    const workflow = {
      nodes: [
        {
          id: 1,
          type,
          service: {},
        },
      ],
    }

    expect(getWorkflowImmediateDispatch(testApp.getRegistry(), workflow)).toBe(
      expected
    )
  })

  test('updates workflow immediate dispatch after replacing the trigger', async () => {
    const trigger = {
      id: 1,
      type: 'local_baserow_rows_created',
      service: {},
    }
    const workflow = {
      id: 2,
      graph: { 0: trigger.id },
      immediate_dispatch: false,
      nodes: [trigger],
      nodeMap: {
        [trigger.id]: trigger,
      },
    }

    testApp.mock.onPost(`automation/node/${trigger.id}/replace/`).reply(200, {
      id: 3,
      type: 'manual',
      service: {},
      workflow: workflow.id,
    })

    await testApp.store.dispatch('automationWorkflowNode/replace', {
      workflow,
      nodeId: trigger.id,
      newType: 'manual',
    })

    expect(workflow.immediate_dispatch).toBe(true)
  })

  test('optimistically updates workflow immediate dispatch while replacing the trigger', async () => {
    const trigger = {
      id: 1,
      type: 'local_baserow_rows_created',
      service: {},
    }
    const workflow = {
      id: 2,
      graph: { 0: trigger.id },
      immediate_dispatch: false,
      nodes: [trigger],
      nodeMap: {
        [trigger.id]: trigger,
      },
    }

    let resolveRequest
    let requestStarted
    const requestStartedPromise = new Promise((resolve) => {
      requestStarted = resolve
    })
    const responsePromise = new Promise((resolve) => {
      resolveRequest = () =>
        resolve([
          200,
          {
            id: 3,
            type: 'manual',
            service: {},
            workflow: workflow.id,
          },
        ])
    })

    testApp.mock.onPost(`automation/node/${trigger.id}/replace/`).reply(() => {
      requestStarted()
      return responsePromise
    })

    const replacePromise = testApp.store.dispatch(
      'automationWorkflowNode/replace',
      {
        workflow,
        nodeId: trigger.id,
        newType: 'manual',
      }
    )

    await requestStartedPromise

    expect(workflow.immediate_dispatch).toBe(true)

    resolveRequest()
    await replacePromise
  })

  test('optimistically updates workflow immediate dispatch while creating a trigger', async () => {
    const workflow = {
      id: 2,
      graph: {},
      immediate_dispatch: false,
      nodes: [],
      nodeMap: {},
      automation_id: 3,
    }

    let resolveRequest
    let requestStarted
    const requestStartedPromise = new Promise((resolve) => {
      requestStarted = resolve
    })
    const responsePromise = new Promise((resolve) => {
      resolveRequest = () =>
        resolve([
          200,
          {
            id: 1,
            type: 'manual',
            service: {},
            workflow: workflow.id,
          },
        ])
    })

    testApp.mock
      .onPost(`automation/workflow/${workflow.id}/nodes/`)
      .reply(() => {
        requestStarted()
        return responsePromise
      })
    testApp.mock
      .onGet(`applications/${workflow.automation_id}/permissions/`)
      .reply(200, {})

    const createPromise = testApp.store.dispatch(
      'automationWorkflowNode/create',
      {
        workflow,
        type: 'manual',
        referenceNode: null,
        position: 'south',
        output: '',
      }
    )

    await requestStartedPromise

    expect(workflow.immediate_dispatch).toBe(true)

    resolveRequest()
    await createPromise
  })

  describe('realtime form-reset metadata', () => {
    const makeWorkflow = () => {
      const node = {
        id: 10,
        type: 'manual',
        service: { foo: 'a' },
        _: { loading: false, viaRealtime: false, realtimeVersion: 0 },
      }
      const workflow = { id: 1, nodes: [node], nodeMap: { 10: node } }
      return { workflow, node }
    }

    test('a realtime (override) update replaces the node, flags it and bumps the version', () => {
      const { workflow } = makeWorkflow()

      nodeStore.mutations.UPDATE_ITEM(
        {},
        {
          workflow,
          node: { id: 10 },
          values: { id: 10, type: 'manual', service: { foo: 'b' } },
          override: true,
          viaRealtime: true,
        }
      )

      const updated = workflow.nodeMap[10]
      expect(updated.service.foo).toBe('b')
      expect(updated._.viaRealtime).toBe(true)
      // Version carried across the object replacement, then bumped once.
      expect(updated._.realtimeVersion).toBe(1)
    })

    test('a local (merge) update clears the flag without bumping the version', () => {
      const { workflow, node } = makeWorkflow()
      node._.viaRealtime = true
      node._.realtimeVersion = 3

      nodeStore.mutations.UPDATE_ITEM(
        {},
        { workflow, node: { id: 10 }, values: { service: { foo: 'c' } } }
      )

      expect(node._.viaRealtime).toBe(false)
      expect(node._.realtimeVersion).toBe(3)
    })
  })
})
