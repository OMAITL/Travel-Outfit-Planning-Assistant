"""Assets node — run Image, Shopping, and Inspiration agents in parallel."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from src.graph.nodes.image import image_node
from src.graph.nodes.inspiration import inspiration_node
from src.graph.nodes.shopping import shopping_node
from src.graph.state import PlanningState


def assets_node(state: PlanningState) -> PlanningState:
    """Generate look images, fetch products, and collect XHS references concurrently."""
    input_errors_len = len(state.errors)
    input_trace_len = len(state.trace)
    state = state.append_trace(
        "Assets",
        "running image, shopping, and inspiration in parallel",
    )

    with ThreadPoolExecutor(max_workers=3) as pool:
        image_future = pool.submit(image_node, state)
        shopping_future = pool.submit(shopping_node, state)
        inspiration_future = pool.submit(inspiration_node, state)
        image_result = image_future.result()
        shopping_result = shopping_future.result()
        inspiration_result = inspiration_future.result()

    child_traces = []
    child_errors = []
    for partial in (image_result, shopping_result, inspiration_result):
        child_traces.extend(partial.trace[input_trace_len:])
        child_errors.extend(partial.errors[input_errors_len:])

    return state.model_copy(
        update={
            "look_images": image_result.look_images,
            "products": shopping_result.products,
            "outfit_inspirations": inspiration_result.outfit_inspirations,
            "errors": [*state.errors, *child_errors],
            "trace": [*state.trace, *child_traces],
        }
    ).append_trace("Assets", "parallel assets complete")
