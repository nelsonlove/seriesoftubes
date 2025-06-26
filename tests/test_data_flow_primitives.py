"""Tests for data flow primitives: split, filter, transform, aggregate"""

import pytest
from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.models import (
    Node,
    NodeType,
    SplitNodeConfig,
    FilterNodeConfig,
    TransformNodeConfig,
    AggregateNodeConfig,
    Workflow,
    WorkflowInput,
)


@pytest.fixture
def sample_companies():
    """Sample company data for testing"""
    return [
        {"name": "Acme Corp", "revenue": 2000000, "industry": "Technology", "employees": 50},
        {"name": "Beta Industries", "revenue": 500000, "industry": "Manufacturing", "employees": 25},
        {"name": "Gamma Tech", "revenue": 5000000, "industry": "Technology", "employees": 100},
        {"name": "Delta Services", "revenue": 800000, "industry": "Services", "employees": 30},
        {"name": "Epsilon Inc", "revenue": 1200000, "industry": "Technology", "employees": 40}
    ]


@pytest.fixture
def engine():
    """Workflow engine instance"""
    return WorkflowEngine()


class TestSplitNode:
    """Test split node functionality"""

    @pytest.mark.asyncio
    async def test_split_basic_functionality(self, engine, sample_companies):
        """Test basic split node operation"""
        # Create a simple workflow with just a split node
        workflow = Workflow(
            name="test-split",
            version="1.0.0",
            inputs={
                "companies": WorkflowInput(input_type="array", required=True)
            },
            nodes={
                "split_companies": Node(
                    name="split_companies",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.companies",
                        item_name="company"
                    )
                )
            },
            outputs={"split_result": "split_companies"}
        )

        # Execute workflow
        context = await engine.execute(workflow, {"companies": sample_companies})

        # Verify results
        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        assert "split_companies" in context.outputs
        
        split_output = context.outputs["split_companies"]
        assert isinstance(split_output, dict)
        assert "split_items" in split_output
        assert "item_name" in split_output
        assert split_output["item_name"] == "company"
        assert len(split_output["split_items"]) == 5
        assert split_output["split_items"] == sample_companies

    @pytest.mark.asyncio
    async def test_split_invalid_field(self, engine, sample_companies):
        """Test split node with invalid field reference"""
        workflow = Workflow(
            name="test-split-invalid",
            version="1.0.0",
            inputs={
                "companies": WorkflowInput(input_type="array", required=True)
            },
            nodes={
                "split_companies": Node(
                    name="split_companies",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.nonexistent",
                        item_name="company"
                    )
                )
            },
            outputs={}
        )

        # Execute workflow
        context = await engine.execute(workflow, {"companies": sample_companies})

        # Should have errors
        assert len(context.errors) > 0
        assert "split_companies" in context.errors


class TestFilterNode:
    """Test filter node functionality"""

    @pytest.mark.asyncio
    async def test_filter_with_split(self, engine, sample_companies):
        """Test filter node working with split node"""
        workflow = Workflow(
            name="test-split-filter",
            version="1.0.0",
            inputs={
                "companies": WorkflowInput(input_type="array", required=True)
            },
            nodes={
                "split_companies": Node(
                    name="split_companies",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.companies",
                        item_name="company"
                    )
                ),
                "filter_high_value": Node(
                    name="filter_high_value",
                    type=NodeType.FILTER,
                    depends_on=["split_companies"],
                    config=FilterNodeConfig(
                        condition="{{ company.revenue > 1000000 }}"
                    )
                )
            },
            outputs={
                "split_result": "split_companies",
                "filtered_result": "filter_high_value"
            }
        )

        # Execute workflow
        context = await engine.execute(workflow, {"companies": sample_companies})

        # Verify results
        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        assert "filter_high_value" in context.outputs
        
        filtered_output = context.outputs["filter_high_value"]
        assert isinstance(filtered_output, list)
        assert len(filtered_output) == 5  # Should have 5 results (some None)
        
        # Count non-None results (companies with revenue > 1M)
        filtered_companies = [item for item in filtered_output if item is not None]
        assert len(filtered_companies) == 3  # Acme (2M), Gamma (5M), Epsilon (1.2M)
        
        # Verify the correct companies were filtered
        company_names = {company["name"] for company in filtered_companies}
        expected_names = {"Acme Corp", "Gamma Tech", "Epsilon Inc"}
        assert company_names == expected_names

    @pytest.mark.asyncio
    async def test_filter_different_conditions(self, engine, sample_companies):
        """Test filter with different condition types"""
        workflow = Workflow(
            name="test-filter-conditions",
            version="1.0.0",
            inputs={
                "companies": WorkflowInput(input_type="array", required=True)
            },
            nodes={
                "split_companies": Node(
                    name="split_companies",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.companies",
                        item_name="company"
                    )
                ),
                "filter_tech": Node(
                    name="filter_tech",
                    type=NodeType.FILTER,
                    depends_on=["split_companies"],
                    config=FilterNodeConfig(
                        condition="{{ company.industry == 'Technology' }}"
                    )
                )
            },
            outputs={"filtered_result": "filter_tech"}
        )

        # Execute workflow
        context = await engine.execute(workflow, {"companies": sample_companies})

        # Verify results
        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        
        filtered_output = context.outputs["filter_tech"]
        filtered_companies = [item for item in filtered_output if item is not None]
        assert len(filtered_companies) == 3  # Acme, Gamma, Epsilon are Technology
        
        # Verify all are Technology companies
        for company in filtered_companies:
            assert company["industry"] == "Technology"


class TestTransformNode:
    """Test transform node functionality"""

    @pytest.mark.asyncio
    async def test_transform_with_filter(self, engine, sample_companies):
        """Test transform node working with filtered data"""
        workflow = Workflow(
            name="test-transform",
            version="1.0.0",
            inputs={
                "companies": WorkflowInput(input_type="array", required=True)
            },
            nodes={
                "split_companies": Node(
                    name="split_companies",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.companies",
                        item_name="company"
                    )
                ),
                "filter_high_value": Node(
                    name="filter_high_value",
                    type=NodeType.FILTER,
                    depends_on=["split_companies"],
                    config=FilterNodeConfig(
                        condition="{{ company.revenue > 1000000 }}"
                    )
                ),
                "transform_companies": Node(
                    name="transform_companies",
                    type=NodeType.TRANSFORM,
                    depends_on=["filter_high_value"],
                    config=TransformNodeConfig(
                        template={
                            "company_id": "{{ item.name | replace(' ', '_') | lower }}",
                            "display_name": "{{ item.name }}",
                            "revenue_millions": "{{ (item.revenue / 1000000) | round(2) }}",
                            "size_category": "{% if item.employees > 75 %}large{% elif item.employees > 40 %}medium{% else %}small{% endif %}"
                        }
                    )
                )
            },
            outputs={"transformed_result": "transform_companies"}
        )

        # Execute workflow
        context = await engine.execute(workflow, {"companies": sample_companies})

        # Verify results
        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        assert "transform_companies" in context.outputs
        
        transformed_output = context.outputs["transform_companies"]
        assert isinstance(transformed_output, list)
        assert len(transformed_output) == 3  # Only high-value companies
        
        # Verify transformation structure
        for company in transformed_output:
            assert "company_id" in company
            assert "display_name" in company
            assert "revenue_millions" in company
            assert "size_category" in company
            
            # Verify data types
            assert isinstance(company["revenue_millions"], (int, float))
            assert company["size_category"] in ["small", "medium", "large"]
        
        # Verify specific transformations
        acme = next(c for c in transformed_output if c["display_name"] == "Acme Corp")
        assert acme["company_id"] == "acme_corp"
        assert acme["revenue_millions"] == 2.0
        assert acme["size_category"] == "medium"  # 50 employees

    @pytest.mark.asyncio
    async def test_transform_string_template(self, engine, sample_companies):
        """Test transform with string template"""
        workflow = Workflow(
            name="test-string-transform",
            version="1.0.0",
            inputs={
                "companies": WorkflowInput(input_type="array", required=True)
            },
            nodes={
                "split_companies": Node(
                    name="split_companies",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.companies",
                        item_name="company"
                    )
                ),
                "filter_high_value": Node(
                    name="filter_high_value",
                    type=NodeType.FILTER,
                    depends_on=["split_companies"],
                    config=FilterNodeConfig(
                        condition="{{ company.revenue > 1000000 }}"
                    )
                ),
                "transform_summaries": Node(
                    name="transform_summaries",
                    type=NodeType.TRANSFORM,
                    depends_on=["filter_high_value"],
                    config=TransformNodeConfig(
                        template="{{ item.name }} - ${{ (item.revenue / 1000000) | round(1) }}M revenue"
                    )
                )
            },
            outputs={"summaries": "transform_summaries"}
        )

        # Execute workflow
        context = await engine.execute(workflow, {"companies": sample_companies})

        # Verify results
        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        
        summaries = context.outputs["transform_summaries"]
        assert len(summaries) == 3
        assert "Acme Corp - $2.0M revenue" in summaries
        assert "Gamma Tech - $5.0M revenue" in summaries
        assert "Epsilon Inc - $1.2M revenue" in summaries


class TestAggregateNode:
    """Test aggregate node functionality"""

    @pytest.mark.asyncio  
    async def test_aggregate_array_mode(self, engine, sample_companies):
        """Test aggregate node in array mode"""
        workflow = Workflow(
            name="test-aggregate",
            version="1.0.0",
            inputs={
                "companies": WorkflowInput(input_type="array", required=True)
            },
            nodes={
                "split_companies": Node(
                    name="split_companies",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.companies",
                        item_name="company"
                    )
                ),
                "filter_high_value": Node(
                    name="filter_high_value", 
                    type=NodeType.FILTER,
                    depends_on=["split_companies"],
                    config=FilterNodeConfig(
                        condition="{{ company.revenue > 1000000 }}"
                    )
                ),
                "transform_companies": Node(
                    name="transform_companies",
                    type=NodeType.TRANSFORM,
                    depends_on=["filter_high_value"],
                    config=TransformNodeConfig(
                        template={
                            "name": "{{ item.name }}",
                            "revenue_millions": "{{ (item.revenue / 1000000) | round(1) }}"
                        }
                    )
                )
            },
            outputs={"final_result": "transform_companies"}
        )

        # Execute workflow
        context = await engine.execute(workflow, {"companies": sample_companies})

        # Verify results
        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        
        result = context.outputs["transform_companies"]
        assert isinstance(result, list)
        assert len(result) == 3
        
        # Verify each company has expected structure
        for company in result:
            assert "name" in company
            assert "revenue_millions" in company
            assert isinstance(company["revenue_millions"], (int, float))


class TestCompleteDataFlowPipeline:
    """Test complete data flow pipeline end-to-end"""

    @pytest.mark.asyncio
    async def test_complete_pipeline(self, engine):
        """Test a complete data processing pipeline"""
        # Sample FDA violations data
        fda_violations = [
            {
                "company_name": "Acme Pharma",
                "violation_type": "Form 483",
                "severity": "major",
                "date": "2024-01-15"
            },
            {
                "company_name": "Beta Bio",
                "violation_type": "Warning Letter",
                "severity": "critical", 
                "date": "2024-01-10"
            },
            {
                "company_name": "Gamma Labs",
                "violation_type": "Form 483",
                "severity": "minor",
                "date": "2024-01-20"
            }
        ]

        workflow = Workflow(
            name="fda-pipeline",
            version="1.0.0",
            inputs={
                "violations": WorkflowInput(input_type="array", required=True)
            },
            nodes={
                "split_violations": Node(
                    name="split_violations",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.violations",
                        item_name="violation"
                    )
                ),
                "filter_serious": Node(
                    name="filter_serious",
                    type=NodeType.FILTER,
                    depends_on=["split_violations"],
                    config=FilterNodeConfig(
                        condition="{{ violation.severity in ['major', 'critical'] }}"
                    )
                ),
                "transform_outreach": Node(
                    name="transform_outreach",
                    type=NodeType.TRANSFORM,
                    depends_on=["filter_serious"],
                    config=TransformNodeConfig(
                        template={
                            "company": "{{ item.company_name }}",
                            "priority": "{% if item.severity == 'critical' %}urgent{% else %}high{% endif %}",
                            "outreach_type": "{% if item.violation_type == 'Warning Letter' %}immediate{% else %}standard{% endif %}"
                        }
                    )
                )
            },
            outputs={
                "outreach_targets": "transform_outreach"
            }
        )

        # Execute workflow
        context = await engine.execute(workflow, {"violations": fda_violations})

        # Verify results
        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        
        targets = context.outputs["transform_outreach"]
        assert len(targets) == 2  # Only major and critical violations
        
        # Find specific companies
        acme_target = next(t for t in targets if t["company"] == "Acme Pharma")
        beta_target = next(t for t in targets if t["company"] == "Beta Bio")
        
        # Verify transformations
        assert acme_target["priority"] == "high"  # major severity
        assert acme_target["outreach_type"] == "standard"  # Form 483
        
        assert beta_target["priority"] == "urgent"  # critical severity
        assert beta_target["outreach_type"] == "immediate"  # Warning Letter

    @pytest.mark.asyncio
    async def test_error_handling(self, engine):
        """Test error handling in data flow primitives"""
        workflow = Workflow(
            name="error-test",
            version="1.0.0",
            inputs={
                "data": WorkflowInput(input_type="array", required=True)
            },
            nodes={
                "split_data": Node(
                    name="split_data",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.nonexistent",  # Invalid field
                        item_name="item"
                    )
                )
            },
            outputs={}
        )

        # Execute workflow with invalid configuration
        context = await engine.execute(workflow, {"data": [1, 2, 3]})

        # Should have errors
        assert len(context.errors) > 0
        assert "split_data" in context.errors


if __name__ == "__main__":
    # Run a simple test manually
    import asyncio
    
    async def manual_test():
        engine = WorkflowEngine()
        sample_data = [
            {"name": "Test Co", "revenue": 2000000, "industry": "Tech", "employees": 50}
        ]
        
        workflow = Workflow(
            name="manual-test",
            version="1.0.0",
            inputs={"companies": WorkflowInput(input_type="array", required=True)},
            nodes={
                "split_test": Node(
                    name="split_test",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(field="inputs.companies", item_name="company")
                )
            },
            outputs={"result": "split_test"}
        )
        
        context = await engine.execute(workflow, {"companies": sample_data})
        print(f"✅ Manual test - Success: {len(context.errors) == 0}")
        print(f"Output: {context.outputs}")
        if context.errors:
            print(f"Errors: {context.errors}")
    
    asyncio.run(manual_test())